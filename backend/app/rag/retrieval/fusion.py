"""Pluggable candidate fusion strategies."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol
from uuid import UUID

from app.rag.retrieval.models import RetrievalCandidate


class FusionStrategy(Protocol):
    @property
    def name(self) -> str: ...

    def fuse(
        self,
        dense: list[RetrievalCandidate],
        sparse: list[RetrievalCandidate],
        exact: list[RetrievalCandidate] | None = None,
    ) -> list[RetrievalCandidate]: ...


class ReciprocalRankFusion:
    def __init__(self, *, k: int = 60) -> None:
        if k < 1:
            raise ValueError("RRF k must be positive")
        self._k = k

    @property
    def name(self) -> str:
        return "rrf"

    def fuse(
        self,
        dense: list[RetrievalCandidate],
        sparse: list[RetrievalCandidate],
        exact: list[RetrievalCandidate] | None = None,
    ) -> list[RetrievalCandidate]:
        candidates: dict[UUID, RetrievalCandidate] = {}
        for item in dense:
            candidates[item.chunk_id] = item
        for item in sparse:
            existing = candidates.get(item.chunk_id)
            candidates[item.chunk_id] = (
                item
                if existing is None
                else replace(
                    existing,
                    sparse_rank=item.sparse_rank,
                    sparse_score=item.sparse_score,
                )
            )
        for item in exact or ():
            existing = candidates.get(item.chunk_id)
            candidates[item.chunk_id] = (
                item
                if existing is None
                else replace(
                    existing,
                    exact_rank=item.exact_rank,
                    exact_score=item.exact_score,
                )
            )
        fused = [
            replace(
                item,
                fusion_score=sum(
                    1 / (self._k + rank)
                    for rank in (item.dense_rank, item.sparse_rank, item.exact_rank)
                    if rank is not None
                ),
            )
            for item in candidates.values()
        ]
        return sorted(
            fused,
            key=lambda item: (
                -item.fusion_score,
                -(item.dense_score or 0.0),
                -(item.sparse_score or 0.0),
                -(item.exact_score or 0.0),
                item.document_key,
                item.version_label,
                item.ordinal,
            ),
        )
