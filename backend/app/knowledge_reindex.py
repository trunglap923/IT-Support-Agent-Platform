"""Controlled re-embedding of committed demo-corpus versions only."""

from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.config import AIProvider, Settings
from app.db import Database
from app.db.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
    DocumentVersionStatus,
    IngestionJob,
)
from app.demo_document_seed import load_demo_corpus
from app.providers.embeddings import EmbeddingProvider
from app.providers.factory import create_embedding_provider
from app.rag.ingestion.pipeline import IngestionPipeline

_SUPPORTED_VECTOR_DIMENSIONS = 1536
_PAID_OPT_IN_VALUES = frozenset({"1", "true", "yes"})


@dataclass(frozen=True, slots=True)
class ReindexTarget:
    document_key: str
    version_label: str
    version_id: UUID
    job_id: UUID
    identity_hash: str


@dataclass(frozen=True, slots=True)
class KnowledgeReindexPlan:
    updated: int
    unchanged: int
    targets: tuple[ReindexTarget, ...]

    @property
    def total(self) -> int:
        return self.updated + self.unchanged


def _reindex_identity(
    version: DocumentVersion,
    *,
    embedding_model: str,
    embedding_dimensions: int,
) -> str:
    value = "\0".join(
        (
            "knowledge-reindex-v1",
            version.source_checksum,
            version.parser_version or "pending-parser",
            version.chunker_version or "pending-chunker",
            embedding_model,
            str(embedding_dimensions),
        )
    )
    return hashlib.sha256(value.encode()).hexdigest()


async def plan_knowledge_reindex(
    database: Database,
    *,
    data_root: Path,
    embedding_model: str,
    embedding_dimensions: int,
) -> KnowledgeReindexPlan:
    """Validate seed ownership and report versions requiring re-embedding."""

    if embedding_dimensions != _SUPPORTED_VECTOR_DIMENSIONS:
        raise ValueError(
            "Re-index dimensions must be 1536 for the current document_chunks vector column"
        )
    specs = load_demo_corpus(data_root)
    expected = {(spec.document_key, spec.version_label): spec for spec in specs}
    document_keys = {document_key for document_key, _ in expected}
    async with database.session() as session:
        rows = (
            await session.execute(
                select(Document, DocumentVersion, IngestionJob)
                .join(DocumentVersion, DocumentVersion.document_id == Document.id)
                .join(IngestionJob, IngestionJob.document_version_id == DocumentVersion.id)
                .where(Document.document_key.in_(document_keys))
            )
        ).all()
        stored = {
            (document.document_key, version.version_label): (document, version, job)
            for document, version, job in rows
        }
        missing = sorted(expected.keys() - stored.keys())
        extras = sorted(stored.keys() - expected.keys())
        if missing:
            raise ValueError(
                "Seed corpus must be applied before re-index; missing versions: "
                + ", ".join(f"{key}:{version}" for key, version in missing)
            )
        if extras:
            raise ValueError(
                "Seed document keys contain unrecognized versions: "
                + ", ".join(f"{key}:{version}" for key, version in extras)
            )

        version_ids = [version.id for _, version, _ in stored.values()]
        chunks = list(
            await session.scalars(
                select(DocumentChunk).where(DocumentChunk.version_id.in_(version_ids))
            )
        )

    chunks_by_version: dict[UUID, list[DocumentChunk]] = {}
    for chunk in chunks:
        chunks_by_version.setdefault(chunk.version_id, []).append(chunk)

    targets: list[ReindexTarget] = []
    unchanged = 0
    for identity in sorted(expected):
        spec = expected[identity]
        document, version, job = stored[identity]
        if not version.storage_key.startswith("seed-corpus/"):
            raise ValueError(f"Refusing to re-index non-seed storage: {spec.document_key}")
        if version.source_checksum != spec.checksum:
            raise ValueError(
                f"Stored seed checksum changed: {spec.document_key}:{spec.version_label}"
            )
        if version.status not in {
            DocumentVersionStatus.PUBLISHED,
            DocumentVersionStatus.SUPERSEDED,
        }:
            raise ValueError(
                f"Seed version is not published/superseded: "
                f"{spec.document_key}:{spec.version_label}"
            )
        version_chunks = chunks_by_version.get(version.id, [])
        matches = (
            bool(version_chunks)
            and version.embedding_model == embedding_model
            and version.embedding_dimensions == embedding_dimensions
            and all(
                chunk.embedding_model == embedding_model
                and chunk.embedding_dimensions == embedding_dimensions
                for chunk in version_chunks
            )
        )
        if matches:
            unchanged += 1
            continue
        targets.append(
            ReindexTarget(
                document_key=document.document_key,
                version_label=version.version_label,
                version_id=version.id,
                job_id=job.id,
                identity_hash=_reindex_identity(
                    version,
                    embedding_model=embedding_model,
                    embedding_dimensions=embedding_dimensions,
                ),
            )
        )
    return KnowledgeReindexPlan(
        updated=len(targets),
        unchanged=unchanged,
        targets=tuple(targets),
    )


async def run_knowledge_reindex(
    database: Database,
    *,
    data_root: Path,
    storage_root: Path,
    embedding_provider: EmbeddingProvider,
    embedding_model: str,
    embedding_dimensions: int,
) -> KnowledgeReindexPlan:
    """Re-embed planned seed versions and atomically replace only their chunks."""

    plan = await plan_knowledge_reindex(
        database,
        data_root=data_root,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
    )
    pipeline = IngestionPipeline(
        database=database,
        embedding_provider=embedding_provider,
        storage_root=storage_root,
    )
    for target in plan.targets:
        async with database.session() as session, session.begin():
            job = await session.get(IngestionJob, target.job_id, with_for_update=True)
            if job is None or job.document_version_id != target.version_id:
                raise RuntimeError(
                    f"Seed ingestion job changed during re-index: "
                    f"{target.document_key}:{target.version_label}"
                )
            job.identity_hash = target.identity_hash
        await pipeline.run(
            target.job_id,
            force=True,
            preserve_version_status=True,
        )

    converged = await plan_knowledge_reindex(
        database,
        data_root=data_root,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dimensions,
    )
    if converged.updated:
        raise RuntimeError("Knowledge re-index did not converge")
    return plan


def format_plan(plan: KnowledgeReindexPlan, *, dry_run: bool) -> str:
    mode = "dry-run" if dry_run else "apply"
    lines = [
        f"Knowledge re-index {mode} validated.",
        f"updated={plan.updated} unchanged={plan.unchanged} total={plan.total}",
    ]
    lines.extend(
        f"- update {target.document_key}:{target.version_label}" for target in plan.targets
    )
    if dry_run:
        lines.append("No chunks, versions or ingestion jobs were modified.")
    return "\n".join(lines)


def _paid_reindex_enabled() -> bool:
    return os.getenv("RUN_PAID_REINDEX", "false").strip().casefold() in _PAID_OPT_IN_VALUES


async def async_main(*, dry_run: bool = False) -> None:
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
        selected_embedding_model = (
            "fake-embedding-v2"
            if settings.embedding_provider is AIProvider.FAKE
            else settings.embedding_model
        )
        plan = await plan_knowledge_reindex(
            database,
            data_root=Path(settings.demo_corpus_path),
            embedding_model=selected_embedding_model,
            embedding_dimensions=settings.embedding_dimensions,
        )
        if dry_run or not plan.updated:
            print(format_plan(plan, dry_run=dry_run))
            return

        provider = create_embedding_provider(settings, database)
        try:
            applied = await run_knowledge_reindex(
                database,
                data_root=Path(settings.demo_corpus_path),
                storage_root=Path(settings.document_storage_path),
                embedding_provider=provider,
                embedding_model=selected_embedding_model,
                embedding_dimensions=settings.embedding_dimensions,
            )
        finally:
            await provider.close()
        print(format_plan(applied, dry_run=False))
    finally:
        await database.close()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Re-embed only the committed seed corpus without resetting the database."
    )
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    asyncio.run(async_main(dry_run=arguments.dry_run))


if __name__ == "__main__":
    main()
