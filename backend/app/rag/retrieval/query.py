"""Exact vector + PostgreSQL FTS retrieval fused with reciprocal rank fusion."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.db.models import Document, DocumentChunk, DocumentVersion
from app.diagnostics import content_log_fields, log_event
from app.providers.embeddings import EmbeddingProvider
from app.rag.retrieval.filters import readable_current_document

_TERM_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
logger = logging.getLogger(__name__)
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
        "bao",
        "bị",
        "bi",
        "cách",
        "cach",
        "cần",
        "cho",
        "có",
        "co",
        "dùng",
        "dung",
        "gì",
        "gi",
        "không",
        "khong",
        "là",
        "la",
        "lý",
        "ly",
        "nào",
        "nao",
        "như",
        "nhu",
        "thế",
        "thì",
        "thi",
        "tôi",
        "toi",
        "trên",
        "tren",
        "và",
        "va",
        "xử",
        "xu",
        "được",
        "duoc",
    }
)

_SUPPORTED_DOMAIN_PATTERN = re.compile(r"\b(?:vpn|docker|registry|gitlab)\b")
_VIETNAMESE_QUERY_EXPANSIONS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (
        re.compile(
            r"\b(?:cấu\s+hình|cau\s+hinh|thiết\s+lập|thiet\s+lap|cài(?:\s+đặt)?|cai(?:\s+dat)?)\b"
        ),
        ("thiết lập", "cài", "setup", "configure", "install"),
    ),
    (
        re.compile(r"\b(?:kết\s+nối|ket\s+noi)\b"),
        ("connect", "connection", "reconnect"),
    ),
    (
        re.compile(r"\b(?:đăng\s+nhập|dang\s+nhap|xác\s+thực|xac\s+thuc)\b"),
        ("authenticate", "authentication", "login", "sso"),
    ),
    (
        re.compile(r"\b(?:chứng\s+chỉ|chung\s+chi)\b"),
        ("certificate", "ca", "bundle"),
    ),
    (
        re.compile(r"\b(?:mã\s+truy\s+cập|ma\s+truy\s+cap|token)\b"),
        ("access", "token"),
    ),
    (
        re.compile(r"\b(?:kho\s+docker|kho\s+chứa|kho\s+chua)\b"),
        ("docker", "registry"),
    ),
    (
        re.compile(r"\b(?:xin\s+quyền|xin\s+quyen|yêu\s+cầu\s+quyền|yeu\s+cau\s+quyen)\b"),
        ("access", "permission", "role"),
    ),
    (
        re.compile(r"\b(?:dự\s+án|du\s+an)\b"),
        ("project",),
    ),
    (
        re.compile(r"\b(?:lỗi|loi)\b"),
        ("error", "troubleshooting"),
    ),
)


def expand_query_for_retrieval(value: str) -> str:
    """Add bounded English aliases for supported-domain Vietnamese queries."""

    normalized = " ".join(value.casefold().split())
    if not _SUPPORTED_DOMAIN_PATTERN.search(normalized):
        return value.strip()

    additions: list[str] = []
    seen = set(_TERM_PATTERN.findall(normalized))
    for pattern, aliases in _VIETNAMESE_QUERY_EXPANSIONS:
        if not pattern.search(normalized):
            continue
        for alias in aliases:
            if alias not in seen:
                additions.append(alias)
                seen.add(alias)
    return " ".join((value.strip(), *additions))


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
    section_path: tuple[str, ...] = ()


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
    section_path: tuple[str, ...]


def _base_query(principal: Principal, *, now: datetime) -> Select[Any]:
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
            DocumentChunk.section_path,
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
        section_path=tuple(mapping["section_path"] or ()),
    )


class HybridRetriever:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        branch_limit: int = 20,
        result_limit: int = 5,
        rrf_k: int = 60,
        log_prompts: bool = False,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._branch_limit = branch_limit
        self._result_limit = result_limit
        self._rrf_k = rrf_k
        self._log_prompts = log_prompts

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
        started_at = time.monotonic()
        expanded_query = expand_query_for_retrieval(query)
        run_id = (
            operation_id.removeprefix("rag:").removesuffix(":retrieve")
            if operation_id.startswith("rag:")
            else None
        )
        log_event(
            logger,
            "retrieval.embedding.started",
            run_id=run_id,
            operation_id=operation_id,
            actor_id=str(principal.user_id),
            query_expanded=expanded_query != query.strip(),
            **content_log_fields(
                "query",
                query,
                include_content=self._log_prompts,
            ),
            **content_log_fields(
                "expanded_query",
                expanded_query,
                include_content=self._log_prompts,
            ),
        )
        query_batch = await self._embedding_provider.embed(
            [expanded_query],
            operation_id=operation_id,
        )
        if query_batch.dimensions != 1536:
            raise ValueError("Query embedding dimensions do not match the corpus")
        query_vector = list(query_batch.vectors[0])
        selected_now = now or datetime.now(UTC)
        base = _base_query(principal, now=selected_now)
        original_query_terms = meaningful_terms(query)
        query_terms = meaningful_terms(expanded_query)

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
            coverage_denominator = len(original_query_terms) or len(query_terms)
            lexical_coverage = (
                min(1.0, len(set(query_terms) & content_terms) / coverage_denominator)
                if coverage_denominator
                else 0.0
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
                    section_path=item.section_path,
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
        results = sorted(
            scored,
            key=lambda hit: (-hit.score, -hit.rrf_score, stable_order[hit.chunk_id]),
        )[: self._result_limit]
        log_event(
            logger,
            "retrieval.search.completed",
            run_id=run_id,
            operation_id=operation_id,
            embedding_model=query_batch.model,
            embedding_request_id=query_batch.provider_request_id,
            vector_candidates=len(vector_rows),
            lexical_candidates=len(lexical_rows),
            result_count=len(results),
            duration_ms=round((time.monotonic() - started_at) * 1_000, 2),
            results=[
                {
                    "chunk_id": str(hit.chunk_id),
                    "document_key": hit.document_key,
                    "version_label": hit.version_label,
                    "title": hit.title,
                    "page_number": hit.page_number,
                    "section": hit.section,
                    "score": round(hit.score, 6),
                    "vector_rank": hit.vector_rank,
                    "lexical_rank": hit.lexical_rank,
                    "vector_similarity": (
                        round(hit.vector_similarity, 6)
                        if hit.vector_similarity is not None
                        else None
                    ),
                    "lexical_coverage": round(hit.lexical_coverage, 6),
                    "rrf_score": round(hit.rrf_score, 6),
                    **content_log_fields(
                        "content",
                        hit.content,
                        include_content=self._log_prompts,
                    ),
                }
                for hit in results
            ],
        )
        return results
