import json

from jsonschema import Draft202012Validator

from app.prompts import (
    MEMORY_EXTRACTION_PROMPT,
    REPLY_SCHEMA,
    SUPPORT_INSTRUCTIONS,
    SUPPORT_PROMPT,
    SUPPORT_PROMPT_VERSION,
    prompt_versions,
)


def test_prompt_assets_are_checksum_verified_and_versioned() -> None:
    assert SUPPORT_PROMPT.read_text() == SUPPORT_INSTRUCTIONS
    assert "check_service_status" in SUPPORT_INSTRUCTIONS
    assert "Never invent corporate policy" in SUPPORT_INSTRUCTIONS
    assert "proposed troubleshooting steps" in MEMORY_EXTRACTION_PROMPT.read_text()
    assert SUPPORT_PROMPT_VERSION == "support-agent-v2"
    assert prompt_versions() == {
        "support_agent": "support-agent-v2",
        "memory_extraction": "memory-extraction-v1",
        "support_reply_schema": "support-reply-v1",
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
