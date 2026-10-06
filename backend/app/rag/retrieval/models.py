"""Provider-neutral contracts for the staged retrieval pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal
from uuid import UUID

VersionScope = Literal["current", "specific", "historical"]
QueryIntent = Literal[
    "knowledge",
    "incident",
    "service_status",
    "identity",
    "ticket_read",
    "ticket_create",
    "social",
    "memory",
    "unknown",
]


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    """Structured constraints extracted from a request before retrieval."""

    services: tuple[str, ...] = ()
    products: tuple[str, ...] = ()
    operating_systems: tuple[str, ...] = ()
    error_codes: tuple[str, ...] = ()
    version_labels: tuple[str, ...] = ()
    version_scope: VersionScope = "current"


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    """Original user request plus retrieval constraints and result budget."""

    raw_query: str
    filters: RetrievalFilters = field(default_factory=RetrievalFilters)
    result_limit: int = 5

    def __post_init__(self) -> None:
        if not self.raw_query.strip():
            raise ValueError("Retrieval query cannot be empty")
        if self.result_limit < 1:
            raise ValueError("Retrieval result limit must be positive")


@dataclass(frozen=True, slots=True)
class QuerySpec:
    """Dense and sparse query forms produced by query analysis.

    ``sparse_query`` deliberately retains the original request so exact technical
    identifiers cannot be lost by semantic normalization.
    """

    raw_query: str
    intent: QueryIntent
    confidence: float
    semantic_query: str
    sparse_query: str
    exact_terms: tuple[str, ...]
    filters: RetrievalFilters
    metadata_filters: tuple[tuple[str, str], ...] = ()
    analyzer: str = "deterministic"

    @classmethod
    def from_request(
        cls,
        request: RetrievalRequest,
        *,
        semantic_query: str | None = None,
        exact_terms: tuple[str, ...] = (),
        intent: QueryIntent = "unknown",
        confidence: float = 0.0,
        filters: RetrievalFilters | None = None,
        metadata_filters: tuple[tuple[str, str], ...] = (),
        analyzer: str = "deterministic",
    ) -> QuerySpec:
        raw_query = request.raw_query.strip()
        return cls(
            raw_query=raw_query,
            intent=intent,
            confidence=max(0.0, min(1.0, confidence)),
            semantic_query=(semantic_query or raw_query).strip(),
            sparse_query=raw_query,
            exact_terms=exact_terms,
            filters=filters or request.filters,
            metadata_filters=metadata_filters,
            analyzer=analyzer,
        )


@dataclass(frozen=True, slots=True)
class RetrievalCandidate:
    """Candidate returned by any dense or sparse provider before final ranking."""

    chunk_id: UUID
    document_id: UUID
    version_id: UUID
    document_key: str
    version_label: str
    content: str
    title: str = ""
    page_number: int | None = None
    section: str | None = None
    ordinal: int = 0
    dense_rank: int | None = None
    sparse_rank: int | None = None
    exact_rank: int | None = None
    dense_score: float | None = None
    sparse_score: float | None = None
    exact_score: float | None = None
    section_id: UUID | None = None
    section_path: tuple[str, ...] = ()
    fusion_score: float = 0.0
    rerank_score: float | None = None
    metadata_score: float = 0.0

    def with_dense(self, *, rank: int, score: float) -> RetrievalCandidate:
        return replace(self, dense_rank=rank, dense_score=score)

    def with_sparse(self, *, rank: int, score: float) -> RetrievalCandidate:
        return replace(self, sparse_rank=rank, sparse_score=score)

    def with_exact(self, *, rank: int, score: float) -> RetrievalCandidate:
        return replace(self, exact_rank=rank, exact_score=score)


@dataclass(frozen=True, slots=True)
class RetrievalContextChunk:
    """Authorized adjacent/parent-section chunk added after seed retrieval."""

    candidate: RetrievalCandidate
    expansion_kind: Literal["neighbor", "parent_section"]


@dataclass(frozen=True, slots=True)
class RankedEvidence:
    """Provider-independent evidence selected after fusion or reranking."""

    candidate: RetrievalCandidate
    rank: int
    score: float
    strategy: str

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("Evidence rank must be positive")
