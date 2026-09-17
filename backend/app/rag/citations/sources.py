"""Build server-owned citations exclusively from authorized retrieval hits."""

from __future__ import annotations

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


def build_evidence_output(
    hits: list[RetrievalHit],
    *,
    requested_source_ids: list[str] | None = None,
    minimum_lexical_coverage: float = 0.5,
    minimum_vector_similarity: float = 0.75,
) -> EvidenceOutput:
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
            excerpt=_excerpt(hit.content),
        )
        for hit in supported
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
        f"page={source.page_number}, section={source.section or 'n/a'}): {source.excerpt}"
        for source in sources
    )
    return EvidenceOutput(outcome="answered", sources=sources, context=context, message=None)
