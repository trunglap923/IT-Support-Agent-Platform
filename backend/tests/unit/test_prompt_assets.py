import json

from jsonschema import Draft202012Validator

from app.prompts import (
    MEMORY_EXTRACTION_PROMPT,
    REPLY_SCHEMA,
    REPLY_SCHEMA_VERSION,
    SUPPORT_INSTRUCTIONS,
    SUPPORT_PROMPT,
    SUPPORT_PROMPT_VERSION,
    prompt_versions,
)


def test_prompt_assets_are_checksum_verified_and_versioned() -> None:
    assert SUPPORT_PROMPT.read_text() == SUPPORT_INSTRUCTIONS
    assert "check_service_status" in SUPPORT_INSTRUCTIONS
    assert "Never invent corporate policy" in SUPPORT_INSTRUCTIONS
    assert "same language as the user's newest query" in SUPPORT_INSTRUCTIONS
    assert "no more than 180 words" in SUPPORT_INSTRUCTIONS
    assert "Never print source IDs" in SUPPORT_INSTRUCTIONS
    assert "do not fill the gap" in SUPPORT_INSTRUCTIONS
    assert "proposed troubleshooting steps" in MEMORY_EXTRACTION_PROMPT.read_text()
    assert SUPPORT_PROMPT_VERSION == "support-agent-v12"
    assert REPLY_SCHEMA_VERSION == "support-reply-v2"
    assert "Markdown numbered" in SUPPORT_INSTRUCTIONS
    assert "do not paste long document" in SUPPORT_INSTRUCTIONS
    assert prompt_versions() == {
        "support_agent": "support-agent-v12",
        "memory_extraction": "memory-extraction-v1",
        "support_reply_schema": "support-reply-v2",
    }


def test_reply_schema_is_valid_and_enforces_citation_outcome() -> None:
    schema = json.loads(REPLY_SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    assert not list(
        validator.iter_errors(
            {"outcome": "answered", "answer": "Use the runbook.", "citations": ["src_1"]}
        )
    )
    assert list(
        validator.iter_errors({"outcome": "answered", "answer": "Unsupported.", "citations": []})
    )
    assert list(
        validator.iter_errors(
            {"outcome": "no_answer", "answer": "Unknown.", "citations": ["src_1"]}
        )
    )
    assert not list(
        validator.iter_errors(
            {
                "outcome": "needs_information",
                "answer": "Bạn đang dùng hệ điều hành nào?",
                "citations": [],
            }
        )
    )
    assert list(
        validator.iter_errors(
            {
                "outcome": "needs_information",
                "answer": "Vui lòng cung cấp hệ điều hành.",
                "citations": [],
            }
        )
    )
