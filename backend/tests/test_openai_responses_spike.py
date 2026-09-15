import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from app.providers.openai_responses_spike import (
    CHECK_SERVICE_STATUS_TOOL,
    MAX_TOTAL_OUTPUT_TOKENS,
    SupportClassification,
    require_live_opt_in,
    run_responses_spike,
)


class StubResponses:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []
        self.parse_calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.create_calls.append(kwargs)
        if "tools" in kwargs:
            return SimpleNamespace(
                id="resp_tool",
                output=[
                    SimpleNamespace(
                        type="function_call",
                        call_id="call_status",
                        name="check_service_status",
                        arguments='{"service":"registry"}',
                    )
                ],
            )
        return SimpleNamespace(id="resp_text", output_text="text-ok")

    async def parse(self, **kwargs: Any) -> Any:
        self.parse_calls.append(kwargs)
        return SimpleNamespace(
            id="resp_structured",
            output_parsed=SupportClassification(category="registry", needs_follow_up=False),
        )


def test_responses_spike_contract_without_network() -> None:
    async def run() -> None:
        responses = StubResponses()
        client = SimpleNamespace(responses=responses)

        result = await run_responses_spike(client=client, model="test-model")

        assert result.text_response_id == "resp_text"
        assert result.structured_category == "registry"
        assert result.tool_call_id == "call_status"
        assert result.tool_service == "registry"
        assert result.max_total_output_tokens == 160

        all_calls = [*responses.create_calls, *responses.parse_calls]
        assert sum(call["max_output_tokens"] for call in all_calls) == MAX_TOTAL_OUTPUT_TOKENS
        assert all(call["store"] is False for call in all_calls)
        tool_call = responses.create_calls[1]
        assert tool_call["parallel_tool_calls"] is False
        assert tool_call["max_tool_calls"] == 1
        assert tool_call["tools"] == [CHECK_SERVICE_STATUS_TOOL]
        assert CHECK_SERVICE_STATUS_TOOL["strict"] is True
        assert CHECK_SERVICE_STATUS_TOOL["parameters"]["additionalProperties"] is False

    asyncio.run(run())


def test_live_spike_requires_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUN_OPENAI_LIVE_SPIKE", raising=False)
    with pytest.raises(SystemExit, match="Refusing paid API calls"):
        require_live_opt_in()

    monkeypatch.setenv("RUN_OPENAI_LIVE_SPIKE", "1")
    require_live_opt_in()
