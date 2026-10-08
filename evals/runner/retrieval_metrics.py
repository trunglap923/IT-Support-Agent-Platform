"""Deterministic, document-level retrieval metrics."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def unique_at_k(ranked: Sequence[str], k: int) -> list[str]:
    """Return the first K unique document-version identifiers."""

    unique: list[str] = []
    seen: set[str] = set()
    for item in ranked:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
        if len(unique) == k:
            break
    return unique


def recall_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    returned = set(unique_at_k(ranked, k))
    return len(returned & relevant) / len(relevant)


def precision_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    if k < 1:
        raise ValueError("K must be positive")
    returned = set(unique_at_k(ranked, k))
    return len(returned & relevant) / k


def reciprocal_rank_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    for rank, item in enumerate(unique_at_k(ranked, k), start=1):
        if item in relevant:
            return 1 / rank
    return 0.0


def ndcg_at_k(ranked: Sequence[str], relevance: Mapping[str, int], k: int) -> float:
    gains = [relevance.get(item, 0) for item in unique_at_k(ranked, k)]
    dcg = sum((2**gain - 1) / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum((2**gain - 1) / math.log2(rank + 1) for rank, gain in enumerate(ideal, 1))
    return dcg / idcg if idcg else 0.0


def duplicate_rate_at_k(ranked: Sequence[str], k: int) -> float:
    window = list(ranked[:k])
    if not window:
        return 0.0
    return (len(window) - len(set(window))) / len(window)
