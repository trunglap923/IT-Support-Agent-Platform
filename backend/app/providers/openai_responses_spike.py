"""Opt-in compatibility probe for the OpenAI Responses API.

This module is deliberately separate from the application runtime. It makes
three small paid requests only after the caller explicitly opts in.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Literal

from openai import AsyncOpenAI
from pydantic import BaseModel

TEXT_MAX_OUTPUT_TOKENS = 32
STRUCTURED_MAX_OUTPUT_TOKENS = 64
TOOL_MAX_OUTPUT_TOKENS = 64
MAX_TOTAL_OUTPUT_TOKENS = (
    TEXT_MAX_OUTPUT_TOKENS + STRUCTURED_MAX_OUTPUT_TOKENS + TOOL_MAX_OUTPUT_TOKENS
)


class SupportClassification(BaseModel):
    category: Literal["vpn", "registry", "gitlab"]
    needs_follow_up: bool


class ServiceStatusArguments(BaseModel):
    service: Literal["vpn", "registry", "gitlab"]


CHECK_SERVICE_STATUS_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "check_service_status",
    "description": "Read the simulated status of one allowlisted IT service.",
    "parameters": {
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "enum": ["vpn", "registry", "gitlab"],
            }
        },
        "required": ["service"],
        "additionalProperties": False,
    },
    "strict": True,
}


@dataclass(frozen=True, slots=True)
class OpenAIResponsesSpikeResult:
    model: str
    text_response_id: str
    structured_response_id: str
    structured_category: str
    tool_response_id: str
    tool_call_id: str
    tool_name: str
    tool_service: str
    max_total_output_tokens: int = MAX_TOTAL_OUTPUT_TOKENS


async def run_responses_spike(
    *,
    client: Any,
    model: str,
) -> OpenAIResponsesSpikeResult:
    """Exercise text, typed output and a side-effect-free function proposal."""

    text_response = await client.responses.create(
        model=model,
        input="Reply with exactly: text-ok",
        max_output_tokens=TEXT_MAX_OUTPUT_TOKENS,
        store=False,
    )
    if not text_response.output_text.strip():
        raise RuntimeError("Responses text generation returned no text")

    structured_response = await client.responses.parse(
        model=model,
        input="Classify this request: Docker registry certificate error.",
        text_format=SupportClassification,
        max_output_tokens=STRUCTURED_MAX_OUTPUT_TOKENS,
        store=False,
    )
    classification = structured_response.output_parsed
    if classification is None:
        raise RuntimeError("Responses structured output returned no parsed object")

    tool_response = await client.responses.create(
        model=model,
        input="Use the tool to check the simulated registry service status.",
        tools=[CHECK_SERVICE_STATUS_TOOL],
        tool_choice={"type": "function", "name": "check_service_status"},
        parallel_tool_calls=False,
        max_tool_calls=1,
        max_output_tokens=TOOL_MAX_OUTPUT_TOKENS,
        store=False,
    )
    tool_calls = [item for item in tool_response.output if item.type == "function_call"]
    if len(tool_calls) != 1:
        raise RuntimeError(f"Expected exactly one function call, received {len(tool_calls)}")

    tool_call = tool_calls[0]
    arguments = ServiceStatusArguments.model_validate_json(tool_call.arguments)
    return OpenAIResponsesSpikeResult(
        model=model,
        text_response_id=text_response.id,
        structured_response_id=structured_response.id,
        structured_category=classification.category,
        tool_response_id=tool_response.id,
        tool_call_id=tool_call.call_id,
        tool_name=tool_call.name,
        tool_service=arguments.service,
    )


def require_live_opt_in() -> None:
    if os.getenv("RUN_OPENAI_LIVE_SPIKE", "").lower() not in {"1", "true", "yes"}:
        raise SystemExit(
            "Refusing paid API calls. Re-run with RUN_OPENAI_LIVE_SPIKE=1 after reviewing "
            "the 160-token output cap."
        )


async def async_main() -> None:
    require_live_opt_in()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required for the opt-in live spike")

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini-2025-04-14")
    client = AsyncOpenAI(api_key=api_key, max_retries=0, timeout=20.0)
    try:
        result = await run_responses_spike(client=client, model=model)
    finally:
        await client.close()

    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
