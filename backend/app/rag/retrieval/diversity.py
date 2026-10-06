"""Bounded document diversity for primary retrieval results."""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.retrieval.models import RetrievalCandidate


@dataclass(frozen=True, slots=True)
class DocumentDiversitySelector:
    """Keep the ranked order while limiting chunks from one document version."""

    max_chunks_per_document: int = 1
    adaptive_max_chunks_per_document: int = 2
    adaptive_score_ratio: float = 0.85

    def __post_init__(self) -> None:
        if self.max_chunks_per_document < 1:
            raise ValueError("Document diversity limit must be positive")
        if self.adaptive_max_chunks_per_document < self.max_chunks_per_document:
            raise ValueError("Adaptive diversity limit cannot be below the base limit")
        if not 0.0 <= self.adaptive_score_ratio <= 1.0:
            raise ValueError("Adaptive score ratio must be between zero and one")

    def select(
        self,
        candidates: list[RetrievalCandidate],
        *,
        limit: int,
        exact_terms: tuple[str, ...] = (),
    ) -> list[RetrievalCandidate]:
        if limit < 1:
            raise ValueError("Result limit must be positive")
        selected: list[RetrievalCandidate] = []
        counts: dict[tuple[object, object], int] = {}
        first_by_document: dict[tuple[object, object], RetrievalCandidate] = {}
        for candidate in candidates:
            key = (candidate.document_id, candidate.version_id)
            count = counts.get(key, 0)
            if count >= self.max_chunks_per_document:
                first = first_by_document[key]
                searchable = " ".join(
                    (
                        candidate.document_key,
                        candidate.title,
                        candidate.section or "",
                        candidate.content,
                    )
                ).casefold()
                same_section = (
                    first.section_id is not None and candidate.section_id == first.section_id
                )
                carries_exact_term = any(term.casefold() in searchable for term in exact_terms)
                first_score = first.rerank_score or first.fusion_score
                candidate_score = candidate.rerank_score or candidate.fusion_score
                strong_enough = candidate_score >= first_score * self.adaptive_score_ratio
                if (
                    count >= self.adaptive_max_chunks_per_document
                    or not strong_enough
                    or not (same_section or carries_exact_term)
                ):
                    continue
            selected.append(candidate)
            counts[key] = count + 1
            first_by_document.setdefault(key, candidate)
            if len(selected) == limit:
                break
        return selected
