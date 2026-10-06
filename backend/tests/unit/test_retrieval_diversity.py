from uuid import UUID

from app.rag.retrieval.diversity import DocumentDiversitySelector
from app.rag.retrieval.models import RetrievalCandidate


def _candidate(
    *,
    chunk: int,
    document: int,
    version: int,
    score: float,
    section: int | None = None,
    content: str | None = None,
) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=UUID(int=chunk),
        document_id=UUID(int=document),
        version_id=UUID(int=version),
        document_key=f"document-{document}",
        version_label=f"v{version}",
        content=content or f"content-{chunk}",
        section_id=UUID(int=section) if section is not None else None,
        rerank_score=score,
    )


def test_diversity_selector_preserves_rank_and_limits_document_versions() -> None:
    candidates = [
        _candidate(chunk=1, document=1, version=1, score=0.9),
        _candidate(chunk=2, document=1, version=1, score=0.8),
        _candidate(chunk=3, document=2, version=1, score=0.7),
        _candidate(chunk=4, document=3, version=1, score=0.6),
    ]

    selected = DocumentDiversitySelector(max_chunks_per_document=1).select(
        candidates,
        limit=3,
    )

    assert [item.chunk_id for item in selected] == [UUID(int=1), UUID(int=3), UUID(int=4)]


def test_diversity_selector_scopes_cap_to_document_version() -> None:
    candidates = [
        _candidate(chunk=1, document=1, version=1, score=0.9),
        _candidate(chunk=2, document=1, version=2, score=0.8),
    ]

    selected = DocumentDiversitySelector(max_chunks_per_document=1).select(
        candidates,
        limit=2,
    )

    assert selected == candidates


def test_diversity_selector_keeps_strong_neighbor_from_same_section() -> None:
    candidates = [
        _candidate(chunk=1, document=1, version=1, score=0.9, section=10),
        _candidate(chunk=2, document=1, version=1, score=0.8, section=10),
        _candidate(chunk=3, document=2, version=1, score=0.7),
    ]

    selected = DocumentDiversitySelector().select(candidates, limit=3)

    assert selected == candidates


def test_diversity_selector_keeps_strong_exact_term_chunk() -> None:
    candidates = [
        _candidate(chunk=1, document=1, version=1, score=0.9),
        _candidate(
            chunk=2,
            document=1,
            version=1,
            score=0.8,
            content="Escalate HTTP-503 with the request ID.",
        ),
        _candidate(chunk=3, document=2, version=1, score=0.7),
    ]

    selected = DocumentDiversitySelector().select(
        candidates,
        limit=3,
        exact_terms=("HTTP-503",),
    )

    assert selected == candidates
