from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.auth.demo_identity import ensure_demo_accounts
from app.db import Database
from app.db.models import DocumentChunk, DocumentVersion
from app.demo_document_seed import seed_published_knowledge
from app.knowledge_reindex import plan_knowledge_reindex, run_knowledge_reindex
from app.providers.embeddings import FakeEmbeddingProvider

NOW = datetime(2026, 9, 17, tzinfo=UTC)


def _data_root() -> Path:
    container_path = Path("/workspace/data")
    if container_path.is_dir():
        return container_path
    return Path(__file__).resolve().parents[3] / "data"


def test_seed_corpus_reindex_is_scoped_dry_runnable_and_idempotent(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_accounts(session, password="knowledge-reindex-password")
            await seed_published_knowledge(
                database,
                data_root=_data_root(),
                storage_root=tmp_path,
                now=NOW,
            )
            async with database.session() as session:
                original_chunk_ids = set(await session.scalars(select(DocumentChunk.id)))

            dry_run = await plan_knowledge_reindex(
                database,
                data_root=_data_root(),
                embedding_model="fake-reindex-v3",
                embedding_dimensions=1536,
            )
            async with database.session() as session:
                after_plan_ids = set(await session.scalars(select(DocumentChunk.id)))

            assert dry_run.updated == 11
            assert dry_run.unchanged == 0
            assert after_plan_ids == original_chunk_ids

            provider = FakeEmbeddingProvider(dimensions=1536, model="fake-reindex-v3")
            applied = await run_knowledge_reindex(
                database,
                data_root=_data_root(),
                storage_root=tmp_path,
                embedding_provider=provider,
                embedding_model="fake-reindex-v3",
                embedding_dimensions=1536,
            )
            second = await run_knowledge_reindex(
                database,
                data_root=_data_root(),
                storage_root=tmp_path,
                embedding_provider=provider,
                embedding_model="fake-reindex-v3",
                embedding_dimensions=1536,
            )
            seeded_again = await seed_published_knowledge(
                database,
                data_root=_data_root(),
                storage_root=tmp_path,
                now=NOW,
            )

            async with database.session() as session:
                chunks = list(await session.scalars(select(DocumentChunk)))
                versions = list(await session.scalars(select(DocumentVersion)))

            assert applied.updated == 11
            assert second.updated == 0
            assert second.unchanged == 11
            assert seeded_again.reused_jobs == 11
            assert {chunk.id for chunk in chunks} == original_chunk_ids
            assert all(chunk.embedding_model == "fake-reindex-v3" for chunk in chunks)
            assert all(chunk.embedding_dimensions == 1536 for chunk in chunks)
            assert all(version.embedding_model == "fake-reindex-v3" for version in versions)
            assert all(version.embedding_dimensions == 1536 for version in versions)
        finally:
            await database.close()

    asyncio.run(scenario())
