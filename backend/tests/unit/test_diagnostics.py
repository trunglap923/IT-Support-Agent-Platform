import json
import logging

from app.diagnostics import content_log_fields, log_event


def test_content_is_hidden_by_default() -> None:
    fields = content_log_fields("prompt", "private VPN details", include_content=False)

    assert "prompt" not in fields
    assert fields["prompt_chars"] == 19
    assert fields["prompt_bytes"] == 19
    assert len(str(fields["prompt_sha256"])) == 16


def test_content_is_bounded_when_explicitly_enabled() -> None:
    fields = content_log_fields("delta", "abcdef", include_content=True, max_chars=3)

    assert fields["delta"] == "abc"
    assert fields["delta_truncated"] is True


def test_log_event_writes_grep_friendly_json(caplog: object) -> None:
    logger = logging.getLogger("test.diagnostics")
    with caplog.at_level(logging.INFO, logger=logger.name):  # type: ignore[attr-defined]
        log_event(logger, "agent.step", run_id="run-1", score=0.75)

    payload = json.loads(caplog.records[-1].message)  # type: ignore[attr-defined]
    assert payload == {
        "event": "agent.step",
        "component": "test.diagnostics",
        "run_id": "run-1",
        "score": 0.75,
    }
