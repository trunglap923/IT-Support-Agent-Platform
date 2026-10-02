"""Build server-owned citations exclusively from authorized retrieval hits."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.rag.retrieval.query import RetrievalHit


class InvalidCitationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Source:
    source_id: str
    source_url: str
    document_id: UUID
    version_id: UUID
    chunk_id: UUID
    document_key: str
    version_label: str
    title: str
    page_number: int | None
    section: str | None
    excerpt: str
    section_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceOutput:
    outcome: Literal["answered", "no_answer"]
    sources: tuple[Source, ...]
    context: tuple[str, ...]
    message: str | None


def source_id_for_chunk(chunk_id: UUID) -> str:
    return f"src_{chunk_id.hex}"


def source_url_for_chunk(chunk_id: UUID) -> str:
    return f"/api/v1/sources/{source_id_for_chunk(chunk_id)}/download"


def _excerpt(content: str, *, limit: int = 500) -> str:
    compact = " ".join(content.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _estimated_tokens(value: str) -> int:
    # Same conservative UTF-8 byte estimate used by the agent context builder.
    return max(1, math.ceil(len(value.encode("utf-8")) / 3))


def _select_hits(
    hits: list[RetrievalHit], *, max_sources: int, context_token_budget: int
) -> list[tuple[RetrievalHit, str]]:
    ranked = sorted(
        enumerate(hits),
        key=lambda item: (
            -(item[1].rerank_score if item[1].rerank_score is not None else item[1].score),
            item[0],
        ),
    )
    selected: list[tuple[RetrievalHit, str]] = []
    selected_content: list[set[str]] = []
    used_tokens = 0
    for _, hit in ranked:
        terms = set(hit.content.casefold().split())
        if any(
            terms and len(terms & prior) / max(1, len(terms | prior)) >= 0.82
            for prior in selected_content
        ):
            continue
        excerpt = _excerpt(hit.content)
        metadata = f"[{source_id_for_chunk(hit.chunk_id)}] {hit.title} ({hit.version_label})"
        cost = _estimated_tokens(metadata + " " + excerpt)
        if used_tokens + cost > context_token_budget:
            metadata_cost = _estimated_tokens(metadata + " ")
            available_bytes = max(0, (context_token_budget - used_tokens - metadata_cost) * 3)
            if available_bytes < 24:
                continue
            excerpt = _excerpt(hit.content, limit=min(500, available_bytes // 3))
            cost = _estimated_tokens(metadata + " " + excerpt)
        if used_tokens + cost > context_token_budget:
            continue
        selected.append((hit, excerpt))
        selected_content.append(terms)
        used_tokens += cost
        if len(selected) >= max_sources:
            break
    return selected


def build_evidence_output(
    hits: list[RetrievalHit],
    *,
    requested_source_ids: list[str] | None = None,
    minimum_lexical_coverage: float = 0.5,
    minimum_vector_similarity: float = 0.75,
    max_sources: int = 5,
    context_token_budget: int = 6_000,
) -> EvidenceOutput:
    if max_sources < 1 or context_token_budget < 1:
        raise ValueError("Evidence source and token budgets must be positive")
    max_sources = min(max_sources, 5)
    supported = [
        hit
        for hit in hits
        if (
            hit.lexical_coverage >= minimum_lexical_coverage
            or (hit.vector_similarity or 0.0) >= minimum_vector_similarity
            or (
                hit.vector_similarity is None
                and hit.lexical_coverage == 0.0
                and hit.score >= minimum_lexical_coverage
            )
        )
    ]
    if not supported:
        return EvidenceOutput(
            outcome="no_answer",
            sources=(),
            context=(),
            message="Không tìm thấy tài liệu hiện hành đủ căn cứ để trả lời.",
        )

    selected_hits = _select_hits(
        supported, max_sources=max_sources, context_token_budget=context_token_budget
    )
    if not selected_hits:
        return EvidenceOutput(
            outcome="no_answer",
            sources=(),
            context=(),
            message="Không tìm thấy tài liệu hiện hành đủ căn cứ để trả lời.",
        )
    sources_by_id = {
        source_id_for_chunk(hit.chunk_id): Source(
            source_id=source_id_for_chunk(hit.chunk_id),
            source_url=source_url_for_chunk(hit.chunk_id),
            document_id=hit.document_id,
            version_id=hit.version_id,
            chunk_id=hit.chunk_id,
            document_key=hit.document_key,
            version_label=hit.version_label,
            title=hit.title,
            page_number=hit.page_number,
            section=hit.section,
            excerpt=excerpt,
            section_path=hit.section_path,
        )
        for hit, excerpt in selected_hits
    }
    selected_ids = requested_source_ids or list(sources_by_id)
    unknown = sorted(set(selected_ids) - sources_by_id.keys())
    if unknown:
        raise InvalidCitationError(
            "Answer referenced source IDs outside the authorized retrieval set"
        )
    if len(selected_ids) != len(set(selected_ids)):
        raise InvalidCitationError("Answer referenced a source more than once")
    sources = tuple(sources_by_id[source_id] for source_id in selected_ids)
    context = tuple(
        f"[{source.source_id}] {source.title} ({source.version_label}, "
        f"page={source.page_number}, section="
        f"{' > '.join(source.section_path) or source.section or 'n/a'}): {source.excerpt}"
        for source in sources
    )
    return EvidenceOutput(outcome="answered", sources=sources, context=context, message=None)
