import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.db.models import UserRole
from app.providers.embeddings import EmbeddingBatch, FakeEmbeddingProvider
from app.rag.retrieval.models import RetrievalCandidate
from app.rag.retrieval.query import HybridRetriever


class RecordingEmbeddingProvider:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self._provider = FakeEmbeddingProvider(dimensions=1536)

    async def embed(self, texts: list[str], *, operation_id: str) -> EmbeddingBatch:
        self.texts.extend(texts)
        return await self._provider.embed(texts, operation_id=operation_id)

    async def close(self) -> None:
        await self._provider.close()


class StubDenseRetriever:
    def __init__(self, result: RetrievalCandidate) -> None:
        self.result = result

    async def retrieve(self, session: AsyncSession, **kwargs: Any) -> list[RetrievalCandidate]:
        return [self.result.with_dense(rank=1, score=0.8)]


class RecordingSparseRetriever:
    def __init__(self, result: RetrievalCandidate) -> None:
        self.result = result
        self.raw_queries: list[str] = []

    async def retrieve(self, session: AsyncSession, **kwargs: Any) -> list[RetrievalCandidate]:
        self.raw_queries.append(str(kwargs["raw_query"]))
        return [self.result.with_sparse(rank=1, score=0.5)]


def test_orchestrator_expands_dense_input_but_preserves_sparse_raw_query() -> None:
    async def scenario() -> None:
        candidate = RetrievalCandidate(
            chunk_id=UUID(int=1),
            document_id=UUID(int=2),
            version_id=UUID(int=3),
            document_key="vpn-setup",
            version_label="v2",
            title="VPN setup",
            content="Cài client VPN được quản lý trên Ubuntu.",
        )
        embeddings = RecordingEmbeddingProvider()
        sparse = RecordingSparseRetriever(candidate)
        retriever = HybridRetriever(
            embedding_provider=embeddings,
            dense_retriever=StubDenseRetriever(candidate),
            sparse_retriever=sparse,
        )
        query = "Cách cấu hình VPN trên Ubuntu?"

        hits = await retriever.search(
            None,  # type: ignore[arg-type]
            query=query,
            principal=Principal(
                user_id=UUID(int=4),
                session_id=UUID(int=5),
                email="user@example.com",
                display_name="User",
                role=UserRole.EMPLOYEE,
                department_id=UUID(int=6),
                department_key="engineering",
            ),
            operation_id="test-hybrid",
            now=datetime(2026, 9, 16, tzinfo=UTC),
        )

        assert sparse.raw_queries == [query]
        assert embeddings.texts[0].startswith(query)
        assert "configure" in embeddings.texts[0]
        assert hits[0].vector_rank == hits[0].lexical_rank == 1
        assert hits[0].rrf_score > 0

    asyncio.run(scenario())
