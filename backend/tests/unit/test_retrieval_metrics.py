import pytest
from evals.runner.retrieval_metrics import (
    duplicate_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank_at_k,
    unique_at_k,
)


def test_metrics_use_unique_document_versions() -> None:
    ranked = ["vpn:v2", "vpn:v2", "troubleshooting:v1", "other:v1"]
    relevant = {"vpn:v2", "troubleshooting:v1"}

    assert unique_at_k(ranked, 3) == ["vpn:v2", "troubleshooting:v1", "other:v1"]
    assert recall_at_k(ranked, relevant, 3) == 1.0
    assert precision_at_k(ranked, relevant, 3) == pytest.approx(2 / 3)
    assert reciprocal_rank_at_k(ranked, relevant, 3) == 1.0
    assert ndcg_at_k(ranked, {"vpn:v2": 3, "troubleshooting:v1": 1}, 3) == 1.0


def test_duplicate_rate_measures_repeated_document_versions() -> None:
    assert duplicate_rate_at_k(["vpn:v2", "vpn:v2", "docker:v1"], 5) == pytest.approx(1 / 3)
    assert duplicate_rate_at_k([], 5) == 0.0
