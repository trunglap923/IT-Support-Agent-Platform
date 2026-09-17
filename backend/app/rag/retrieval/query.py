"""Exact vector + PostgreSQL FTS retrieval fused with reciprocal rank fusion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.db.models import Document, DocumentChunk, DocumentVersion
from app.providers.embeddings import EmbeddingProvider
from app.rag.retrieval.filters import readable_current_document

_TERM_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_QUERY_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "can",
        "company",
        "demo",
        "does",
        "for",
        "from",
        "how",
        "i",
        "is",
        "of",
        "on",
        "the",
        "to",
        "use",
        "what",
        "which",
        "with",
        "báo",
        "bị",
        "cách",
        "cần",
        "cho",
        "có",
        "dùng",
        "gì",
        "không",
        "là",
        "lý",
        "nào",
        "như",
        "thế",
        "thì",
        "tôi",
        "trên",
        "và",
        "xử",
        "được",
    }
)


def meaningful_terms(value: str, *, limit: int = 24) -> tuple[str, ...]:
    """Return stable Unicode search terms without natural-language filler words."""

    terms: list[str] = []
    seen: set[str] = set()
    for token in _TERM_PATTERN.findall(value.casefold()):
        if len(token) < 2 or token in _QUERY_STOP_WORDS or token in seen:
            continue
        seen.add(token)
        terms.append(token)
        if len(terms) == limit:
            break
    return tuple(terms)


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    document_key: str
    version_label: str
    title: str
    page_number: int | None
    section: str | None
    content: str
    score: float
    vector_rank: int | None
    lexical_rank: int | None
    vector_similarity: float | None = None
    lexical_coverage: float = 0.0
    rrf_score: float = 0.0


@dataclass(frozen=True, slots=True)
class _Candidate:
    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    document_key: str
    version_label: str
    title: str
    page_number: int | None
    section: str | None
    content: str
    ordinal: int


def _base_query(
    principal: Principal, *, now: datetime
) -> Select[tuple[UUID, UUID, UUID, str, str, str, int | None, str | None, str, int]]:
    return (
        select(
            DocumentChunk.id.label("chunk_id"),
            Document.id.label("document_id"),
            DocumentVersion.id.label("version_id"),
            Document.document_key,
            DocumentVersion.version_label,
            Document.title,
            DocumentChunk.page_number,
            DocumentChunk.section,
            DocumentChunk.content,
            DocumentChunk.ordinal,
        )
        .join(DocumentVersion, DocumentChunk.version_id == DocumentVersion.id)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(readable_current_document(principal, now=now))
    )


def _candidate(row: object) -> _Candidate:
    mapping = row._mapping  # type: ignore[attr-defined]
    return _Candidate(
        chunk_id=mapping["chunk_id"],
        document_id=mapping["document_id"],
        version_id=mapping["version_id"],
        document_key=mapping["document_key"],
        version_label=mapping["version_label"],
        title=mapping["title"],
        page_number=mapping["page_number"],
        section=mapping["section"],
        content=mapping["content"],
        ordinal=mapping["ordinal"],
    )


class HybridRetriever:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        branch_limit: int = 20,
        result_limit: int = 5,
        rrf_k: int = 60,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._branch_limit = branch_limit
        self._result_limit = result_limit
        self._rrf_k = rrf_k

    async def search(
        self,
        session: AsyncSession,
        *,
        query: str,
        principal: Principal,
        operation_id: str,
        now: datetime | None = None,
    ) -> list[RetrievalHit]:
        if not query.strip():
            raise ValueError("Retrieval query cannot be empty")
        query_batch = await self._embedding_provider.embed([query], operation_id=operation_id)
        if query_batch.dimensions != 1536:
            raise ValueError("Query embedding dimensions do not match the corpus")
        query_vector = list(query_batch.vectors[0])
        selected_now = now or datetime.now(UTC)
        base = _base_query(principal, now=selected_now)
        query_terms = meaningful_terms(query)

        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        vector_rows = (
            await session.execute(
                base.add_columns(distance.label("vector_distance"))
                .order_by(
                    distance,
                    Document.document_key,
                    DocumentVersion.version_label,
                    DocumentChunk.ordinal,
                )
                .limit(self._branch_limit)
            )
        ).all()

        lexical_rows: list[Any] = []
        if query_terms:
            ts_query = func.to_tsquery("simple", " | ".join(query_terms))
            lexical_score = func.ts_rank_cd(DocumentChunk.search_vector, ts_query)
            lexical_rows = list(
                (
                    await session.execute(
                        base.add_columns(lexical_score.label("lexical_score"))
                        .where(DocumentChunk.search_vector.op("@@")(ts_query))
                        .order_by(
                            lexical_score.desc(),
                            Document.document_key,
                            DocumentVersion.version_label,
                            DocumentChunk.ordinal,
                        )
                        .limit(self._branch_limit)
                    )
                ).all()
            )

        candidates: dict[UUID, _Candidate] = {}
        vector_ranks: dict[UUID, int] = {}
        vector_similarities: dict[UUID, float] = {}
        lexical_ranks: dict[UUID, int] = {}
        for rank, row in enumerate(vector_rows, start=1):
            item = _candidate(row)
            candidates[item.chunk_id] = item
            vector_ranks[item.chunk_id] = rank
            distance_value = float(row._mapping["vector_distance"])
            vector_similarities[item.chunk_id] = max(0.0, min(1.0, 1.0 - distance_value))
        for rank, lexical_row in enumerate(lexical_rows, start=1):
            item = _candidate(lexical_row)
            candidates[item.chunk_id] = item
            lexical_ranks[item.chunk_id] = rank

        scored: list[RetrievalHit] = []
        for chunk_id, item in candidates.items():
            vector_rank = vector_ranks.get(chunk_id)
            lexical_rank = lexical_ranks.get(chunk_id)
            rrf_score = sum(
                1 / (self._rrf_k + rank) for rank in (vector_rank, lexical_rank) if rank is not None
            )
            content_terms = set(meaningful_terms(item.content, limit=800))
            lexical_coverage = (
                len(set(query_terms) & content_terms) / len(query_terms) if query_terms else 0.0
            )
            vector_similarity = vector_similarities.get(chunk_id)
            score = max(vector_similarity or 0.0, lexical_coverage)
            scored.append(
                RetrievalHit(
                    chunk_id=item.chunk_id,
                    document_id=item.document_id,
                    version_id=item.version_id,
                    document_key=item.document_key,
                    version_label=item.version_label,
                    title=item.title,
                    page_number=item.page_number,
                    section=item.section,
                    content=item.content,
                    score=score,
                    vector_rank=vector_rank,
                    lexical_rank=lexical_rank,
                    vector_similarity=vector_similarity,
                    lexical_coverage=lexical_coverage,
                    rrf_score=rrf_score,
                )
            )
        stable_order = {
            candidate.chunk_id: (
                candidate.document_key,
                candidate.version_label,
                candidate.ordinal,
            )
            for candidate in candidates.values()
        }
        return sorted(
            scored,
            key=lambda hit: (-hit.score, -hit.rrf_score, stable_order[hit.chunk_id]),
        )[: self._result_limit]
