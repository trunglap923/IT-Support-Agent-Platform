"""Dependency-free document-ranking metrics compatible with standard BEIR definitions."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueryMetrics:
    ndcg_at_10: float
    map_at_10: float
    recall_at_5: float
    recall_at_10: float
    precision_at_10: float
    mrr_at_10: float


def _relevant(qrels: Mapping[str, int]) -> set[str]:
    return {document_id for document_id, score in qrels.items() if score > 0}


def _dcg(ranking: Sequence[str], qrels: Mapping[str, int], k: int) -> float:
    return sum(
        (2 ** qrels.get(document_id, 0) - 1) / math.log2(rank + 1)
        for rank, document_id in enumerate(ranking[:k], start=1)
    )


def query_metrics(ranking: Sequence[str], qrels: Mapping[str, int]) -> QueryMetrics:
    relevant = _relevant(qrels)
    if not relevant:
        raise ValueError("A public benchmark query must have a positive relevance judgment")
    ideal_scores = sorted((score for score in qrels.values() if score > 0), reverse=True)
    ideal_dcg = sum(
        (2**score - 1) / math.log2(rank + 1)
        for rank, score in enumerate(ideal_scores[:10], start=1)
    )
    hits = 0
    precision_sum = 0.0
    reciprocal_rank = 0.0
    for rank, document_id in enumerate(ranking[:10], start=1):
        if document_id in relevant:
            hits += 1
            precision_sum += hits / rank
            if reciprocal_rank == 0.0:
                reciprocal_rank = 1.0 / rank
    return QueryMetrics(
        ndcg_at_10=_dcg(ranking, qrels, 10) / ideal_dcg if ideal_dcg else 0.0,
        map_at_10=precision_sum / min(len(relevant), 10),
        recall_at_5=len(set(ranking[:5]) & relevant) / len(relevant),
        recall_at_10=len(set(ranking[:10]) & relevant) / len(relevant),
        precision_at_10=len(set(ranking[:10]) & relevant) / 10,
        mrr_at_10=reciprocal_rank,
    )


def aggregate_metrics(
    rankings: Mapping[str, Sequence[str]],
    qrels: Mapping[str, Mapping[str, int]],
) -> dict[str, float]:
    if set(rankings) != set(qrels):
        missing = sorted(set(qrels) - set(rankings))
        extra = sorted(set(rankings) - set(qrels))
        raise ValueError(f"Ranking/query mismatch; missing={missing[:1]}, extra={extra[:1]}")
    values = [query_metrics(rankings[query_id], judgments) for query_id, judgments in qrels.items()]
    if not values:
        raise ValueError("Cannot aggregate an empty public benchmark")
    return {
        field: sum(getattr(item, field) for item in values) / len(values)
        for field in QueryMetrics.__dataclass_fields__
    }
