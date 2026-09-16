import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from app.auth.principal import Principal
from app.db import Database
from app.db.models import (
    Department,
    Document,
    DocumentChunk,
    DocumentVersion,
    DocumentVersionStatus,
    DocumentVisibility,
    UserRole,
)
from app.providers.embeddings import FakeEmbeddingProvider
from app.rag.retrieval.query import HybridRetriever


def test_hybrid_retrieval_filters_scope_and_old_versions(migrated_database_url: str) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        embeddings = FakeEmbeddingProvider(dimensions=1536)
        try:
            async with database.session() as session, session.begin():
                engineering = Department(key="engineering", name="Engineering")
                operations = Department(key="operations", name="Operations")
                session.add_all([engineering, operations])
                await session.flush()
                documents = [
                    Document(
                        document_key="registry-policy",
                        title="Registry policy",
                        visibility=DocumentVisibility.COMPANY,
                        department_id=None,
                    ),
                    Document(
                        document_key="engineering-notes",
                        title="Engineering notes",
                        visibility=DocumentVisibility.DEPARTMENT,
                        department_id=engineering.id,
                    ),
                    Document(
                        document_key="it-recovery",
                        title="IT recovery",
                        visibility=DocumentVisibility.IT_ONLY,
                        department_id=None,
                    ),
                ]
                session.add_all(documents)
                await session.flush()
                versions: list[DocumentVersion] = []
                for document in documents:
                    version = DocumentVersion(
                        document_id=document.id,
                        version_label="v2",
                        status=DocumentVersionStatus.PUBLISHED,
                        authority="it",
                        language="en",
                        media_type="application/pdf",
                        source_checksum=hashlib.sha256(document.document_key.encode()).hexdigest(),
                        storage_key=f"{document.document_key}.pdf",
                        effective_at=datetime(2026, 1, 1, tzinfo=UTC),
                        parser_version="test",
                        chunker_version="test",
                        embedding_model="fake-embedding-v1",
                        embedding_dimensions=1536,
                    )
                    session.add(version)
                    await session.flush()
                    document.current_version_id = version.id
                    versions.append(version)
                old = DocumentVersion(
                    document_id=documents[0].id,
                    version_label="v1",
                    status=DocumentVersionStatus.SUPERSEDED,
                    authority="it",
                    language="en",
                    media_type="application/pdf",
                    source_checksum="a" * 64,
                    storage_key="registry-old.pdf",
                    effective_at=datetime(2025, 1, 1, tzinfo=UTC),
                    parser_version="test",
                    chunker_version="test",
                    embedding_model="fake-embedding-v1",
                    embedding_dimensions=1536,
                )
                session.add(old)
                await session.flush()
                texts = [
                    "Registry token expires after eight hours current policy",
                    "Engineering registry incident secret department procedure",
                    "IT registry recovery operator procedure",
                    "Registry token lasts thirty days retired policy",
                ]
                vectors = await embeddings.embed(texts, operation_id="seed")
                for ordinal, (version, content, vector) in enumerate(
                    zip([*versions, old], texts, vectors.vectors, strict=True)
                ):
                    session.add(
                        DocumentChunk(
                            id=uuid4(),
                            version_id=version.id,
                            ordinal=0,
                            page_number=1,
                            section="Policy",
                            source_path=version.storage_key,
                            source_token_start=0,
                            source_token_end=len(content.split()),
                            content=content,
                            token_count=len(content.split()),
                            content_hash=hashlib.sha256(
                                f"{ordinal}:{content}".encode()
                            ).hexdigest(),
                            embedding_model="fake-embedding-v1",
                            embedding_dimensions=1536,
                            embedding=list(vector),
                        )
                    )
                operations_principal = Principal(
                    user_id=uuid4(),
                    session_id=uuid4(),
                    email="ops@example.com",
                    display_name="Ops",
                    role=UserRole.EMPLOYEE,
                    department_id=operations.id,
                    department_key="operations",
                )

            async with database.session() as session:
                hits = await HybridRetriever(embedding_provider=embeddings, result_limit=10).search(
                    session,
                    query="registry token policy",
                    principal=operations_principal,
                    operation_id="query-1",
                    now=datetime(2026, 9, 16, tzinfo=UTC),
                )
                assert {hit.document_key for hit in hits} == {"registry-policy"}
                assert {hit.version_label for hit in hits} == {"v2"}
                assert all("secret" not in hit.content for hit in hits)
                assert all("operator" not in hit.content for hit in hits)
                assert all("thirty days" not in hit.content for hit in hits)
        finally:
            await database.close()

    asyncio.run(scenario())
