"""Dense retrieval branch implementations."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.db.models import Document, DocumentChunk, DocumentVersion
from app.rag.retrieval.models import RetrievalCandidate
from app.rag.retrieval.store import candidate_from_row, scoped_chunk_query


class DenseRetriever(Protocol):
    async def retrieve(
        self,
        session: AsyncSession,
        *,
        query_vector: list[float],
        principal: Principal,
        now: datetime,
        limit: int,
    ) -> list[RetrievalCandidate]: ...


class PostgresDenseRetriever:
    """Exact cosine retrieval over authorized, current leaf chunks."""

    async def retrieve(
        self,
        session: AsyncSession,
        *,
        query_vector: list[float],
        principal: Principal,
        now: datetime,
        limit: int,
    ) -> list[RetrievalCandidate]:
        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        rows = (
            await session.execute(
                scoped_chunk_query(principal, now=now)
                .add_columns(distance.label("vector_distance"))
                .order_by(
                    distance,
                    Document.document_key,
                    DocumentVersion.version_label,
                    DocumentChunk.ordinal,
                )
                .limit(limit)
            )
        ).all()
        return [
            _with_dense_rank(candidate_from_row(row), rank, float(row._mapping["vector_distance"]))
            for rank, row in enumerate(rows, start=1)
        ]


def _with_dense_rank(
    candidate: RetrievalCandidate, rank: int, distance: float
) -> RetrievalCandidate:
    return candidate.with_dense(rank=rank, score=max(0.0, min(1.0, 1.0 - distance)))
