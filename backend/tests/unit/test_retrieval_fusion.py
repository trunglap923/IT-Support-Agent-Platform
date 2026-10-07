from uuid import UUID

import pytest

from app.rag.retrieval.fusion import ReciprocalRankFusion
from app.rag.retrieval.models import RetrievalCandidate


def candidate(value: int, key: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=UUID(int=value),
        document_id=UUID(int=value + 100),
        version_id=UUID(int=value + 200),
        document_key=key,
        version_label="v1",
        content=key,
    )


def test_rrf_merges_branch_metadata_and_ranks_shared_candidate_first() -> None:
    shared = candidate(1, "shared").with_dense(rank=2, score=0.6)
    dense_only = candidate(2, "dense").with_dense(rank=1, score=0.99)
    sparse_shared = candidate(1, "shared").with_sparse(rank=1, score=0.8)
    sparse_only = candidate(3, "sparse").with_sparse(rank=2, score=0.7)

    fused = ReciprocalRankFusion(k=60).fuse([dense_only, shared], [sparse_shared, sparse_only])

    assert [item.document_key for item in fused] == ["shared", "dense", "sparse"]
    assert fused[0].dense_rank == 2
    assert fused[0].sparse_rank == 1
    assert fused[0].fusion_score == pytest.approx(1 / 62 + 1 / 61)


def test_rrf_merges_exact_branch_rank_and_score() -> None:
    shared = candidate(1, "shared").with_dense(rank=1, score=0.7)
    exact_shared = candidate(1, "shared").with_exact(rank=1, score=1.0)
    sparse_only = candidate(2, "sparse").with_sparse(rank=1, score=0.9)

    fused = ReciprocalRankFusion(k=60).fuse(
        [shared],
        [sparse_only],
        [exact_shared],
    )

    assert fused[0].document_key == "shared"
    assert fused[0].exact_rank == 1
    assert fused[0].exact_score == 1.0
    assert fused[0].fusion_score == pytest.approx(2 / 61)


def test_weighted_rrf_can_prioritize_a_stronger_dense_branch() -> None:
    dense_only = candidate(1, "dense").with_dense(rank=1, score=0.99)
    shared = candidate(2, "shared").with_dense(rank=20, score=0.5)
    sparse_shared = candidate(2, "shared").with_sparse(rank=20, score=0.8)

    equal = ReciprocalRankFusion(k=60).fuse([dense_only, shared], [sparse_shared])
    weighted = ReciprocalRankFusion(
        k=60,
        dense_weight=1.0,
        sparse_weight=0.25,
        exact_weight=0.0,
    ).fuse([dense_only, shared], [sparse_shared])

    assert equal[0].document_key == "shared"
    assert weighted[0].document_key == "dense"
    assert weighted[0].fusion_score == pytest.approx(1 / 61)
    assert weighted[0].fusion_score > weighted[1].fusion_score
    assert weighted[0].dense_rank == 1
    assert weighted[0].sparse_rank is None
    assert weighted[1].fusion_score == pytest.approx(1.25 / 80)
    assert weighted[1].dense_rank == weighted[1].sparse_rank == 20
    assert (
        ReciprocalRankFusion(dense_weight=1.0, sparse_weight=0.25, exact_weight=0.0).name
        == "weighted_rrf:dense=1,sparse=0.25,exact=0"
    )


@pytest.mark.parametrize("value", [0, -1])
def test_rrf_rejects_non_positive_k(value: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        ReciprocalRankFusion(k=value)


@pytest.mark.parametrize(
    ("weights", "message"),
    [((-1.0, 1.0, 1.0), "non-negative"), ((0.0, 0.0, 0.0), "positive")],
)
def test_rrf_rejects_invalid_branch_weights(
    weights: tuple[float, float, float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        ReciprocalRankFusion(
            dense_weight=weights[0], sparse_weight=weights[1], exact_weight=weights[2]
        )
