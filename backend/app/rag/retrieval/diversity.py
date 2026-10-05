"""Bounded document diversity for primary retrieval results."""

from __future__ import annotations

from dataclasses import dataclass

from app.rag.retrieval.models import RetrievalCandidate


@dataclass(frozen=True, slots=True)
class DocumentDiversitySelector:
    """Keep the ranked order while limiting chunks from one document version."""

    max_chunks_per_document: int = 1

    def __post_init__(self) -> None:
        if self.max_chunks_per_document < 1:
            raise ValueError("Document diversity limit must be positive")

    def select(
        self,
        candidates: list[RetrievalCandidate],
        *,
        limit: int,
    ) -> list[RetrievalCandidate]:
        if limit < 1:
            raise ValueError("Result limit must be positive")
        selected: list[RetrievalCandidate] = []
        counts: dict[tuple[object, object], int] = {}
        for candidate in candidates:
            key = (candidate.document_id, candidate.version_id)
            if counts.get(key, 0) >= self.max_chunks_per_document:
                continue
            selected.append(candidate)
            counts[key] = counts.get(key, 0) + 1
            if len(selected) == limit:
                break
        return selected
