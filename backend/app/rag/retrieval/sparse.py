"""Sparse retrieval branch implementations."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

import bm25s  # type: ignore[import-untyped]
import Stemmer  # type: ignore[import-not-found]
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


class Bm25SparseRetriever:
    """In-memory BM25 over one principal's authorized current-document snapshot.

    A retriever instance belongs to one Agent run. It never shares an index across
    principals, which keeps the server-side ACL boundary intact. Repeated searches
    in the same run reuse the snapshot and index.
    """

    def __init__(self, *, k1: float = 0.9, b: float = 0.4) -> None:
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("BM25 requires k1 > 0 and 0 <= b <= 1")
        self._k1 = k1
        self._b = b
        self._scope: tuple[object, ...] | None = None
        self._candidates: list[RetrievalCandidate] = []
        self._retriever: object | None = None

    @staticmethod
    def _search_text(candidate: RetrievalCandidate) -> str:
        return "\n".join(
            part.strip()
            for part in (candidate.title, candidate.section or "", candidate.content)
            if part.strip()
        )

    def _build_index(self, candidates: list[RetrievalCandidate]) -> object | None:
        if not candidates:
            return None
        corpus_tokens = bm25s.tokenize(
            [self._search_text(candidate) for candidate in candidates],
            stopwords="en",
            stemmer=Stemmer.Stemmer("english"),
            show_progress=False,
        )
        retriever = bm25s.BM25(k1=self._k1, b=self._b, method="lucene")
        retriever.index(corpus_tokens, show_progress=False)
        return retriever

    def _search(self, raw_query: str, limit: int) -> list[tuple[int, float]]:
        if self._retriever is None or not self._candidates:
            return []
        query_tokens = bm25s.tokenize(
            [raw_query],
            stopwords="en",
            stemmer=Stemmer.Stemmer("english"),
            show_progress=False,
        )
        retrieved = self._retriever.retrieve(  # type: ignore[attr-defined]
            query_tokens,
            k=min(limit, len(self._candidates)),
            show_progress=False,
        )
        return [
            (int(index), float(score))
            for index, score in zip(
                retrieved.documents[0].tolist(),
                retrieved.scores[0].tolist(),
                strict=True,
            )
            if float(score) > 0
        ]

    async def retrieve(
        self,
        session: AsyncSession,
        *,
        raw_query: str,
        principal: Principal,
        now: datetime,
        limit: int,
    ) -> list[RetrievalCandidate]:
        if limit < 1 or not raw_query.strip():
            return []
        scope = (
            principal.user_id,
            principal.role,
            principal.department_id,
        )
        if self._scope is not None and self._scope != scope:
            raise RuntimeError("A BM25 sparse retriever cannot be shared across ACL scopes")
        if self._scope is None:
            rows = list((await session.execute(scoped_chunk_query(principal, now=now))).all())
            self._candidates = [candidate_from_row(row) for row in rows]
            self._retriever = self._build_index(self._candidates)
            self._scope = scope
        ranked = self._search(raw_query, limit)
        return [
            self._candidates[index].with_sparse(rank=rank, score=score)
            for rank, (index, score) in enumerate(ranked, start=1)
        ]


def create_sparse_retriever(*, strategy: str) -> SparseRetriever:
    if strategy == "postgres_fts":
        return PostgresSparseRetriever()
    if strategy == "bm25":
        return Bm25SparseRetriever()
    raise ValueError(f"Unsupported sparse retrieval backend: {strategy}")
