"""Exact vector + PostgreSQL FTS retrieval fused with reciprocal rank fusion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.db.models import Document, DocumentChunk, DocumentVersion
from app.providers.embeddings import EmbeddingProvider
from app.rag.retrieval.filters import readable_current_document


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

        ts_query = func.plainto_tsquery("simple", query)
        lexical_score = func.ts_rank_cd(DocumentChunk.search_vector, ts_query)
        lexical_rows = (
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

        candidates: dict[UUID, _Candidate] = {}
        vector_ranks: dict[UUID, int] = {}
        lexical_ranks: dict[UUID, int] = {}
        for rank, row in enumerate(vector_rows, start=1):
            item = _candidate(row)
            candidates[item.chunk_id] = item
            vector_ranks[item.chunk_id] = rank
        for rank, row in enumerate(lexical_rows, start=1):
            item = _candidate(row)
            candidates[item.chunk_id] = item
            lexical_ranks[item.chunk_id] = rank

        scored: list[RetrievalHit] = []
        for chunk_id, item in candidates.items():
            vector_rank = vector_ranks.get(chunk_id)
            lexical_rank = lexical_ranks.get(chunk_id)
            score = sum(
                1 / (self._rrf_k + rank) for rank in (vector_rank, lexical_rank) if rank is not None
            )
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
        return sorted(scored, key=lambda hit: (-hit.score, stable_order[hit.chunk_id]))[
            : self._result_limit
        ]
