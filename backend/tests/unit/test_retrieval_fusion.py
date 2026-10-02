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


@pytest.mark.parametrize("value", [0, -1])
def test_rrf_rejects_non_positive_k(value: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        ReciprocalRankFusion(k=value)
