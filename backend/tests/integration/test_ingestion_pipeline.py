import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select

from app.db import Database
from app.db.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
    DocumentVersionStatus,
    DocumentVisibility,
    IngestionJob,
    IngestionJobStatus,
)
from app.providers.embeddings import EmbeddingBatch, FakeEmbeddingProvider
from app.rag.ingestion.pipeline import IngestionPipeline
from tests.unit.pdf_factory import build_text_pdf


class CountingEmbeddingProvider:
    def __init__(self) -> None:
        self.calls = 0
        self._provider = FakeEmbeddingProvider(dimensions=1536)

    async def embed(self, texts: list[str], *, operation_id: str) -> EmbeddingBatch:
        self.calls += 1
        return await self._provider.embed(texts, operation_id=operation_id)


def test_ingestion_retry_is_idempotent(migrated_database_url: str, tmp_path: Path) -> None:
    async def scenario() -> None:
        storage_key = "vpn.pdf"
        content = build_text_pdf("VPN setup uses SSO and the managed client.")
        (tmp_path / storage_key).write_bytes(content)
        database = Database(migrated_database_url)
        provider = CountingEmbeddingProvider()
        try:
            async with database.session() as session, session.begin():
                document = Document(
                    document_key="vpn-setup",
                    title="VPN setup",
                    visibility=DocumentVisibility.COMPANY,
                    department_id=None,
                )
                session.add(document)
                await session.flush()
                version = DocumentVersion(
                    document_id=document.id,
                    version_label="v1",
                    status=DocumentVersionStatus.DRAFT,
                    authority="it",
                    language="en",
                    media_type="application/pdf",
                    source_checksum=hashlib.sha256(content).hexdigest(),
                    storage_key=storage_key,
                    effective_at=datetime(2026, 1, 1, tzinfo=UTC),
                )
                session.add(version)
                await session.flush()
                job = IngestionJob(
                    document_version_id=version.id,
                    identity_hash="d" * 64,
                    status=IngestionJobStatus.DRAFT,
                )
                session.add(job)
                await session.flush()
                job_id, version_id = job.id, version.id

            pipeline = IngestionPipeline(
                database=database, embedding_provider=provider, storage_root=tmp_path
            )
            first = await pipeline.run(job_id)
            second = await pipeline.run(job_id)
            assert not first.reused
            assert second.reused
            assert provider.calls == 1
            async with database.session() as session:
                count = await session.scalar(
                    select(func.count(DocumentChunk.id)).where(
                        DocumentChunk.version_id == version_id
                    )
                )
                stored_job = await session.get(IngestionJob, job_id)
                assert count == first.chunk_count
                assert stored_job is not None
                assert stored_job.status is IngestionJobStatus.COMPLETED
        finally:
            await database.close()

    asyncio.run(scenario())
