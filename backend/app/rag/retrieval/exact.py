"""ACL-scoped exact lexical candidate retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy import Float, case, func, literal, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.db.models import Document, DocumentChunk, DocumentVersion
from app.rag.retrieval.analysis import meaningful_terms
from app.rag.retrieval.models import RetrievalCandidate
from app.rag.retrieval.store import candidate_from_row, scoped_chunk_query


class ExactRetriever(Protocol):
    async def retrieve(
        self,
        session: AsyncSession,
        *,
        raw_query: str,
        exact_terms: tuple[str, ...],
        principal: Principal,
        now: datetime,
        limit: int,
    ) -> list[RetrievalCandidate]: ...


class PostgresExactRetriever:
    """Rank literal query tokens across chunk content and document metadata.

    Unlike PostgreSQL FTS, this branch preserves punctuation-bearing identifiers and
    also sees title, document key, section, and version metadata. It is a bounded
    candidate branch; it never bypasses the shared ACL/current-version predicate.
    """

    async def retrieve(
        self,
        session: AsyncSession,
        *,
        raw_query: str,
        exact_terms: tuple[str, ...],
        principal: Principal,
        now: datetime,
        limit: int,
    ) -> list[RetrievalCandidate]:
        terms = tuple(
            dict.fromkeys(
                term.casefold().strip()
                for term in (*exact_terms, *meaningful_terms(raw_query))
                if term.strip()
            )
        )
        if not terms:
            return []
        searchable = func.lower(
            func.concat_ws(
                " ",
                Document.document_key,
                Document.title,
                DocumentVersion.version_label,
                DocumentChunk.section,
                DocumentChunk.content,
            )
        )
        matches = [func.strpos(searchable, term) > 0 for term in terms]
        match_count = sum(
            (case((condition, 1), else_=0) for condition in matches),
            literal(0),
        )
        exact_score = match_count.cast(Float) / len(terms)
        rows = (
            await session.execute(
                scoped_chunk_query(principal, now=now)
                .add_columns(exact_score.label("exact_score"))
                .where(or_(*matches))
                .order_by(
                    exact_score.desc(),
                    Document.document_key,
                    DocumentVersion.version_label,
                    DocumentChunk.ordinal,
                )
                .limit(limit)
            )
        ).all()
        return [
            candidate_from_row(row).with_exact(
                rank=rank,
                score=float(row._mapping["exact_score"]),
            )
            for rank, row in enumerate(rows, start=1)
        ]
