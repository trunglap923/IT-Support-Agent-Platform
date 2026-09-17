from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select, update

from app.auth.demo_identity import ensure_demo_accounts
from app.auth.principal import Principal
from app.db import Database
from app.db.models import (
    Document,
    DocumentChunk,
    DocumentVersion,
    DocumentVersionStatus,
    DocumentVisibility,
    IngestionJob,
    IngestionJobStatus,
    User,
)
from app.demo_document_seed import plan_published_knowledge, seed_published_knowledge
from app.providers.embeddings import FakeEmbeddingProvider
from app.rag.chunking.splitter import CHUNKER_VERSION
from app.rag.citations.sources import build_evidence_output
from app.rag.retrieval.query import HybridRetriever
from app.services.documents import DocumentUploadService

NOW = datetime(2026, 9, 17, tzinfo=UTC)


def _data_root() -> Path:
    container_path = Path("/workspace/data")
    if container_path.is_dir():
        return container_path
    return Path(__file__).resolve().parents[3] / "data"


def test_demo_corpus_is_published_idempotently_with_scoped_retrieval(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_accounts(session, password="demo-document-test-password")

            first = await seed_published_knowledge(
                database,
                data_root=_data_root(),
                storage_root=tmp_path,
                now=NOW,
            )
            async with database.session() as session:
                first_chunk_ids = set(await session.scalars(select(DocumentChunk.id)))
            second = await seed_published_knowledge(
                database,
                data_root=_data_root(),
                storage_root=tmp_path,
                now=NOW,
            )

            async with database.session() as session:
                documents = list((await session.scalars(select(Document))).all())
                versions = list((await session.scalars(select(DocumentVersion))).all())
                jobs = list((await session.scalars(select(IngestionJob))).all())
                chunks = list((await session.scalars(select(DocumentChunk))).all())
                users = {user.email: user for user in await session.scalars(select(User))}
                department_keys = {
                    document.department_id
                    for document in documents
                    if document.visibility is DocumentVisibility.DEPARTMENT
                }

                def principal(email: str, department_key: str) -> Principal:
                    user = users[email]
                    return Principal(
                        user_id=user.id,
                        session_id=UUID(int=0),
                        email=user.email,
                        display_name=user.display_name,
                        role=user.role,
                        department_id=user.department_id,
                        department_key=department_key,
                    )

                retriever = HybridRetriever(
                    embedding_provider=FakeEmbeddingProvider(dimensions=1536),
                    branch_limit=50,
                    result_limit=50,
                )
                operations_hits = await retriever.search(
                    session,
                    query="Engineering on-call Registry incident IT operators restart VPN",
                    principal=principal("employee.operations@example.com", "operations"),
                    operation_id="demo-corpus-operations",
                    now=NOW,
                )
                engineering_hits = await retriever.search(
                    session,
                    query="Engineering on-call Registry incident",
                    principal=principal("employee.engineering@example.com", "engineering"),
                    operation_id="demo-corpus-engineering",
                    now=NOW,
                )
                it_hits = await retriever.search(
                    session,
                    query="IT operators restart simulated VPN gateway Engineering on-call",
                    principal=principal("it.engineering@example.com", "engineering"),
                    operation_id="demo-corpus-it",
                    now=NOW,
                )
                natural_language_hits = await retriever.search(
                    session,
                    query=(
                        "Tôi dùng Ubuntu và VPN báo certificate warning. Tôi cần xử lý thế nào?"
                    ),
                    principal=principal("employee.engineering@example.com", "engineering"),
                    operation_id="demo-corpus-natural-language",
                    now=NOW,
                )
                natural_language_evidence = build_evidence_output(natural_language_hits)

                vpn_document = next(
                    document for document in documents if document.document_key == "vpn-setup"
                )
                vpn_version = next(
                    version for version in versions if version.id == vpn_document.current_version_id
                )
                preview = await DocumentUploadService(
                    storage_root=tmp_path,
                    max_pdf_bytes=10 * 1024 * 1024,
                    max_pdf_pages=100,
                    max_extracted_text_bytes=1024 * 1024,
                ).preview(
                    session,
                    document_id=vpn_document.id,
                    version_id=vpn_version.id,
                )
                duplicate_ordinals = await session.scalar(
                    select(func.count())
                    .select_from(DocumentChunk)
                    .group_by(DocumentChunk.version_id, DocumentChunk.ordinal)
                    .having(func.count() > 1)
                    .limit(1)
                )

            assert first.document_count == second.document_count == 9
            assert first.version_count == second.version_count == 11
            assert first.published_count == second.published_count == 9
            assert first.chunk_count == second.chunk_count == len(chunks)
            assert first.reused_jobs == 0
            assert second.reused_jobs == 11
            assert set(chunk.id for chunk in chunks) == first_chunk_ids
            assert duplicate_ordinals is None
            assert len(documents) == 9
            assert len(versions) == len(jobs) == 11
            assert (
                sum(version.status is DocumentVersionStatus.PUBLISHED for version in versions) == 9
            )
            assert (
                sum(version.status is DocumentVersionStatus.SUPERSEDED for version in versions) == 2
            )
            assert all(job.status is IngestionJobStatus.COMPLETED for job in jobs)
            assert all(chunk.embedding_model == "fake-embedding-v2" for chunk in chunks)
            assert len(department_keys) == 1

            operations_keys = {hit.document_key for hit in operations_hits}
            engineering_keys = {hit.document_key for hit in engineering_hits}
            it_keys = {hit.document_key for hit in it_hits}
            assert "engineering-oncall" not in operations_keys
            assert "it-service-recovery" not in operations_keys
            assert "engineering-oncall" in engineering_keys
            assert "it-service-recovery" not in engineering_keys
            assert {"engineering-oncall", "it-service-recovery"} <= it_keys
            assert natural_language_evidence.outcome == "answered"
            assert natural_language_evidence.sources[0].document_key == "vpn-troubleshooting"
            assert preview is not None
            assert preview.parser_version == "markdown-sections-v1"
            assert len(preview.pages) >= 3
        finally:
            await database.close()

    asyncio.run(scenario())


def test_demo_seed_refreshes_completed_jobs_when_chunker_is_stale(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_accounts(session, password="demo-document-test-password")

            await seed_published_knowledge(
                database,
                data_root=_data_root(),
                storage_root=tmp_path,
                now=NOW,
            )
            async with database.session() as session, session.begin():
                await session.execute(
                    update(DocumentVersion).values(chunker_version="word-window-v1")
                )

            stale = await plan_published_knowledge(
                database,
                data_root=_data_root(),
                now=NOW,
            )
            assert stale.updated == stale.version_count == 11

            refreshed = await seed_published_knowledge(
                database,
                data_root=_data_root(),
                storage_root=tmp_path,
                now=NOW,
            )
            converged = await plan_published_knowledge(
                database,
                data_root=_data_root(),
                now=NOW,
            )
            second = await seed_published_knowledge(
                database,
                data_root=_data_root(),
                storage_root=tmp_path,
                now=NOW,
            )

            async with database.session() as session:
                versions = list(await session.scalars(select(DocumentVersion)))
                jobs = list(await session.scalars(select(IngestionJob)))

            assert refreshed.reused_jobs == 0
            assert converged.updated == 0
            assert converged.unchanged == converged.version_count == 11
            assert second.reused_jobs == 11
            assert all(version.chunker_version == CHUNKER_VERSION for version in versions)
            assert all(
                version.status
                in {DocumentVersionStatus.PUBLISHED, DocumentVersionStatus.SUPERSEDED}
                for version in versions
            )
            assert all(job.status is IngestionJobStatus.COMPLETED for job in jobs)
        finally:
            await database.close()

    asyncio.run(scenario())
