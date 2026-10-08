"""Backfill model-identified embeddings for active durable memory."""

from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AIProvider, Settings
from app.db import Database
from app.db.models import (
    IncidentEpisode,
    MemoryAssertion,
    Procedure,
    ProcedureApplicability,
    ProcedureStep,
    ProcedureVersion,
)
from app.providers.embeddings import EmbeddingProvider
from app.providers.factory import create_embedding_provider

_PAID_OPT_IN_VALUES = frozenset({"1", "true", "yes"})


@dataclass(frozen=True, slots=True)
class MemoryReindexPlan:
    semantic: int
    episodic: int
    procedural: int

    @property
    def total(self) -> int:
        return self.semantic + self.episodic + self.procedural


async def plan_memory_reindex(database: Database) -> MemoryReindexPlan:
    async with database.session() as session:
        semantic = len(
            list(
                await session.scalars(
                    select(MemoryAssertion.id).where(
                        MemoryAssertion.status == "active",
                        MemoryAssertion.deleted_at.is_(None),
                        MemoryAssertion.embedding.is_(None),
                    )
                )
            )
        )
        episodic = len(
            list(
                await session.scalars(
                    select(IncidentEpisode.id).where(
                        IncidentEpisode.deleted_at.is_(None),
                        IncidentEpisode.embedding.is_(None),
                    )
                )
            )
        )
        procedural = len(
            list(
                await session.scalars(
                    select(ProcedureVersion.id).where(
                        ProcedureVersion.status == "approved",
                        ProcedureVersion.embedding.is_(None),
                    )
                )
            )
        )
    return MemoryReindexPlan(semantic=semantic, episodic=episodic, procedural=procedural)


async def _embed(
    provider: EmbeddingProvider,
    text: str,
    *,
    operation_id: str,
) -> tuple[list[float], str, int]:
    batch = await provider.embed([text], operation_id=operation_id)
    if batch.dimensions != 1536 or len(batch.vectors) != 1:
        raise RuntimeError("Memory re-index embedding response has an unexpected shape")
    return list(batch.vectors[0]), batch.model, batch.dimensions


async def run_memory_reindex(
    database: Database,
    *,
    embedding_provider: EmbeddingProvider,
) -> MemoryReindexPlan:
    execution_id = uuid4()
    semantic_count = 0
    episodic_count = 0
    procedural_count = 0
    async with database.session() as session, session.begin():
        assertions = list(
            await session.scalars(
                select(MemoryAssertion)
                .where(
                    MemoryAssertion.status == "active",
                    MemoryAssertion.deleted_at.is_(None),
                    MemoryAssertion.embedding.is_(None),
                )
                .with_for_update()
            )
        )
        for assertion in assertions:
            vector, model, dimensions = await _embed(
                embedding_provider,
                assertion.normalized_text,
                operation_id=f"memory-reindex:{execution_id}:assertion:{assertion.id}",
            )
            assertion.embedding = vector
            assertion.embedding_model = model
            assertion.embedding_dimensions = dimensions
            semantic_count += 1

        episodes = list(
            await session.scalars(
                select(IncidentEpisode)
                .where(
                    IncidentEpisode.deleted_at.is_(None),
                    IncidentEpisode.embedding.is_(None),
                )
                .with_for_update()
            )
        )
        for episode in episodes:
            vector, model, dimensions = await _embed(
                embedding_provider,
                episode.summary,
                operation_id=f"memory-reindex:{execution_id}:episode:{episode.id}",
            )
            episode.embedding = vector
            episode.embedding_model = model
            episode.embedding_dimensions = dimensions
            episodic_count += 1

        procedure_rows = (
            await session.execute(
                select(ProcedureVersion, Procedure)
                .join(Procedure, Procedure.id == ProcedureVersion.procedure_id)
                .where(
                    ProcedureVersion.status == "approved",
                    ProcedureVersion.embedding.is_(None),
                )
                .with_for_update()
            )
        ).all()
        for version, procedure in procedure_rows:
            text = await _procedure_text(session, version.id, procedure)
            vector, model, dimensions = await _embed(
                embedding_provider,
                text,
                operation_id=f"memory-reindex:{execution_id}:procedure:{version.id}",
            )
            version.embedding = vector
            version.embedding_model = model
            version.embedding_dimensions = dimensions
            procedural_count += 1
    return MemoryReindexPlan(
        semantic=semantic_count,
        episodic=episodic_count,
        procedural=procedural_count,
    )


async def _procedure_text(session: AsyncSession, version_id: UUID, procedure: Procedure) -> str:
    signals = list(
        await session.scalars(
            select(ProcedureApplicability.signal_value).where(
                ProcedureApplicability.procedure_version_id == version_id
            )
        )
    )
    actions = list(
        await session.scalars(
            select(ProcedureStep.action)
            .where(ProcedureStep.procedure_version_id == version_id)
            .order_by(ProcedureStep.ordinal)
        )
    )
    return "\n".join((procedure.title, procedure.intent, procedure.description, *signals, *actions))


def _format(plan: MemoryReindexPlan, *, dry_run: bool) -> str:
    mode = "dry-run" if dry_run else "apply"
    return (
        f"Memory re-index {mode}: total={plan.total} semantic={plan.semantic} "
        f"episodic={plan.episodic} procedural={plan.procedural}"
    )


def _paid_reindex_enabled() -> bool:
    return os.getenv("RUN_PAID_REINDEX", "false").strip().casefold() in _PAID_OPT_IN_VALUES


async def async_main(*, dry_run: bool) -> None:
    settings = Settings()
    if settings.database_url is None:
        raise SystemExit("DATABASE_URL is required")
    if (
        settings.embedding_provider is AIProvider.OPENAI
        and not dry_run
        and not _paid_reindex_enabled()
    ):
        raise SystemExit("OpenAI re-index is paid; set RUN_PAID_REINDEX=1 for this command only")
    database = Database(settings.database_url.get_secret_value())
    try:
        if dry_run:
            print(_format(await plan_memory_reindex(database), dry_run=True))
            return
        provider = create_embedding_provider(settings, database)
        try:
            result = await run_memory_reindex(database, embedding_provider=provider)
        finally:
            await provider.close()
        print(_format(result, dry_run=False))
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(async_main(dry_run=arguments.dry_run))


if __name__ == "__main__":
    main()
