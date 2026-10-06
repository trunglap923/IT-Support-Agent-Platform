from __future__ import annotations

import math

import pytest
from evals.public.metrics import aggregate_metrics, query_metrics


def test_query_metrics_use_graded_ndcg_and_binary_relevance_metrics() -> None:
    metrics = query_metrics(["d2", "x", "d1"], {"d1": 3, "d2": 1})
    actual_dcg = 1.0 + 7.0 / math.log2(4)
    ideal_dcg = 7.0 + 1.0 / math.log2(3)

    assert metrics.ndcg_at_10 == pytest.approx(actual_dcg / ideal_dcg)
    assert metrics.map_at_10 == pytest.approx((1.0 + 2 / 3) / 2)
    assert metrics.recall_at_5 == 1.0
    assert metrics.recall_at_10 == 1.0
    assert metrics.precision_at_10 == 0.2
    assert metrics.mrr_at_10 == 1.0


def test_aggregate_metrics_macro_averages_queries() -> None:
    metrics = aggregate_metrics(
        {"q1": ["d1"], "q2": ["x", "d2"]},
        {"q1": {"d1": 1}, "q2": {"d2": 1}},
    )

    assert metrics["recall_at_10"] == 1.0
    assert metrics["mrr_at_10"] == 0.75


def test_aggregate_metrics_requires_every_official_query() -> None:
    with pytest.raises(ValueError, match="Ranking/query mismatch"):
        aggregate_metrics({}, {"q1": {"d1": 1}})
