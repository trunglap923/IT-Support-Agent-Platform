from uuid import uuid4

import pytest

from app.rag.citations.sources import (
    InvalidCitationError,
    build_evidence_output,
    source_id_for_chunk,
)
from app.rag.retrieval.query import RetrievalHit


def hit(
    *,
    score: float = 0.8,
    content: str = "Use the managed VPN client.",
    vector_similarity: float | None = None,
    lexical_coverage: float = 0.0,
    section_path: tuple[str, ...] = (),
) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        version_id=uuid4(),
        document_key="vpn-setup",
        version_label="v2",
        title="VPN setup",
        page_number=2,
        section="Ubuntu",
        content=content,
        score=score,
        vector_rank=1,
        lexical_rank=1,
        vector_similarity=vector_similarity,
        lexical_coverage=lexical_coverage,
        section_path=section_path,
    )


def test_builds_traceable_source_from_retrieval_hit() -> None:
    retrieval_hit = hit()

    output = build_evidence_output([retrieval_hit])

    assert output.outcome == "answered"
    assert output.sources[0].source_id == source_id_for_chunk(retrieval_hit.chunk_id)
    assert output.sources[0].source_url.endswith(
        f"/{source_id_for_chunk(retrieval_hit.chunk_id)}/download"
    )
    assert output.sources[0].page_number == 2
    assert output.sources[0].version_id == retrieval_hit.version_id
    assert output.sources[0].excerpt == retrieval_hit.content


def test_context_uses_full_section_path() -> None:
    output = build_evidence_output([hit(section_path=("VPN", "Ubuntu", "Authentication"))])

    assert output.sources[0].section_path == ("VPN", "Ubuntu", "Authentication")
    assert "section=VPN > Ubuntu > Authentication" in output.context[0]


def test_rejects_source_not_present_in_retrieval_results() -> None:
    retrieval_hit = hit()

    with pytest.raises(InvalidCitationError, match="outside"):
        build_evidence_output(
            [retrieval_hit],
            requested_source_ids=[source_id_for_chunk(uuid4())],
        )


@pytest.mark.parametrize("hits", [[], [hit(score=0.49)]])
def test_no_answer_when_evidence_is_missing_or_below_threshold(
    hits: list[RetrievalHit],
) -> None:
    output = build_evidence_output(hits)

    assert output.outcome == "no_answer"
    assert output.sources == ()
    assert output.context == ()
    assert output.message is not None


def test_no_answer_when_both_explicit_evidence_signals_are_weak() -> None:
    output = build_evidence_output([hit(score=0.8, vector_similarity=0.70, lexical_coverage=0.33)])

    assert output.outcome == "no_answer"


@pytest.mark.parametrize(
    ("vector_similarity", "lexical_coverage"),
    [(0.75, 0.0), (0.0, 0.5)],
)
def test_answer_when_an_explicit_evidence_signal_reaches_its_threshold(
    vector_similarity: float,
    lexical_coverage: float,
) -> None:
    output = build_evidence_output(
        [
            hit(
                score=max(vector_similarity, lexical_coverage),
                vector_similarity=vector_similarity,
                lexical_coverage=lexical_coverage,
            )
        ]
    )

    assert output.outcome == "answered"


def test_excerpt_is_bounded() -> None:
    output = build_evidence_output([hit(content="word " * 200)])
    assert len(output.sources[0].excerpt) == 500
    assert output.sources[0].excerpt.endswith("…")
