"""Sparse retrieval branch implementations."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.db.models import Document, DocumentChunk, DocumentVersion
from app.rag.retrieval.analysis import meaningful_terms
from app.rag.retrieval.models import RetrievalCandidate
from app.rag.retrieval.store import candidate_from_row, scoped_chunk_query


class SparseRetriever(Protocol):
    async def retrieve(
        self,
        session: AsyncSession,
        *,
        raw_query: str,
        principal: Principal,
        now: datetime,
        limit: int,
    ) -> list[RetrievalCandidate]: ...


class PostgresSparseRetriever:
    """PostgreSQL FTS branch that always tokenizes the original user query."""

    async def retrieve(
        self,
        session: AsyncSession,
        *,
        raw_query: str,
        principal: Principal,
        now: datetime,
        limit: int,
    ) -> list[RetrievalCandidate]:
        terms = meaningful_terms(raw_query)
        if not terms:
            return []
        ts_query = func.to_tsquery("simple", " | ".join(terms))
        sparse_score = func.ts_rank_cd(DocumentChunk.search_vector, ts_query)
        rows = list(
            (
                await session.execute(
                    scoped_chunk_query(principal, now=now)
                    .add_columns(sparse_score.label("sparse_score"))
                    .where(DocumentChunk.search_vector.op("@@")(ts_query))
                    .order_by(
                        sparse_score.desc(),
                        Document.document_key,
                        DocumentVersion.version_label,
                        DocumentChunk.ordinal,
                    )
                    .limit(limit)
                )
            ).all()
        )
        return [
            candidate_from_row(row).with_sparse(
                rank=rank, score=float(row._mapping["sparse_score"])
            )
            for rank, row in enumerate(rows, start=1)
        ]
