from evals.runner.retrieval_baseline import RelevantChunk, load_cases


def test_phase5_retrieval_cases_include_chunk_and_citation_labels() -> None:
    cases = load_cases()
    answerable = [case for case in cases if case.expected_outcome == "answered"]

    assert len(cases) == 42
    assert len(answerable) >= 30
    assert all(case.relevant_chunks for case in answerable)
    assert {"semantic_vi", "semantic_en", "mixed_vi_en", "acl", "no_answer"} <= {
        tag for case in cases for tag in case.tags
    }


def test_relevant_chunk_requires_document_section_and_terms() -> None:
    label = RelevantChunk(
        document_key="vpn-setup",
        version_label="v2",
        section="Ubuntu",
        required_terms=["SSO", "client"],
    )

    assert label.matches(
        document_key="vpn-setup",
        version_label="v2",
        section="Ubuntu",
        content="Cài managed client rồi đăng nhập SSO.",
    )
    assert not label.matches(
        document_key="vpn-setup",
        version_label="v2",
        section="Windows",
        content="Install client and authenticate with SSO.",
    )
