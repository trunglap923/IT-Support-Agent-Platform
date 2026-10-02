"""Deterministic query-aware reranking for a bounded hybrid candidate pool."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from app.rag.retrieval.analysis import meaningful_terms
from app.rag.retrieval.models import RetrievalCandidate


class Reranker(Protocol):
    @property
    def name(self) -> str: ...

    def rerank(
        self, query: str, candidates: list[RetrievalCandidate]
    ) -> list[RetrievalCandidate]: ...


class WeightedFeatureReranker:
    """Rerank using query-term coverage, exact identifier overlap, and RRF.

    This is a cheap, deterministic baseline. It deliberately exposes an interface
    so a measured cross-encoder can replace it without changing retrieval callers.
    """

    @property
    def name(self) -> str:
        return "weighted_feature_v1"

    def rerank(
        self, query: str, candidates: list[RetrievalCandidate]
    ) -> list[RetrievalCandidate]:
        query_terms = tuple(dict.fromkeys(meaningful_terms(query)))
        exact_terms = tuple(
            term.casefold()
            for term in query.split()
            if any(char.isdigit() for char in term) or any(char in "._-/\\" for char in term)
        )
        max_rrf = max((item.fusion_score for item in candidates), default=0.0) or 1.0
        ranked: list[RetrievalCandidate] = []
        for candidate in candidates:
            searchable = " ".join(
                (candidate.title, candidate.section or "", " ".join(candidate.section_path), candidate.content)
            ).casefold()
            content_terms = set(meaningful_terms(searchable, limit=1_000))
            coverage = len(set(query_terms) & content_terms) / len(query_terms) if query_terms else 0.0
            identifier_match = (
                sum(term in searchable for term in exact_terms) / len(exact_terms)
                if exact_terms
                else 0.0
            )
            normalized_rrf = candidate.fusion_score / max_rrf
            dense = candidate.dense_score or 0.0
            score = 0.55 * coverage + 0.25 * identifier_match + 0.15 * normalized_rrf + 0.05 * dense
            ranked.append(replace(candidate, rerank_score=score))
        return sorted(
            ranked,
            key=lambda item: (
                -(item.rerank_score or 0.0),
                -item.fusion_score,
                item.document_key,
                item.ordinal,
            ),
        )
