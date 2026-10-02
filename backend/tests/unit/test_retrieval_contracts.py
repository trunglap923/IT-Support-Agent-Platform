from uuid import uuid4

import pytest

from app.rag.retrieval.models import (
    QuerySpec,
    RankedEvidence,
    RetrievalCandidate,
    RetrievalFilters,
    RetrievalRequest,
)


def test_query_spec_preserves_original_sparse_query_and_exact_terms() -> None:
    request = RetrievalRequest(
        raw_query="  VPN-1042 trên GlobalProtect 6.1  ",
        filters=RetrievalFilters(
            services=("vpn",),
            operating_systems=("ubuntu",),
            error_codes=("VPN-1042",),
        ),
    )

    spec = QuerySpec.from_request(
        request,
        semantic_query="vpn connection failure",
        exact_terms=("VPN-1042", "GlobalProtect 6.1"),
    )

    assert spec.raw_query == "VPN-1042 trên GlobalProtect 6.1"
    assert spec.sparse_query == spec.raw_query
    assert spec.semantic_query == "vpn connection failure"
    assert spec.exact_terms == ("VPN-1042", "GlobalProtect 6.1")
    assert spec.filters is request.filters


@pytest.mark.parametrize("query", ["", "   "])
def test_retrieval_request_rejects_empty_query(query: str) -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        RetrievalRequest(raw_query=query)


def test_ranked_evidence_requires_positive_rank() -> None:
    candidate = RetrievalCandidate(
        chunk_id=uuid4(),
        document_id=uuid4(),
        version_id=uuid4(),
        document_key="vpn-setup",
        version_label="v2",
        content="content",
    )

    with pytest.raises(ValueError, match="rank must be positive"):
        RankedEvidence(candidate=candidate, rank=0, score=1.0, strategy="rrf")
