"""OpenAI Responses API adapter."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI

from app.prompts import SUPPORT_INSTRUCTIONS
from app.providers.base import GeneratedText
from app.providers.structured import (
    EvidenceInput,
    ProviderContractError,
    StructuredModelResponse,
    SupportReply,
    SupportToolCall,
    ToolDecisionResponse,
    validate_reply_sources,
)
from app.services.budget.service import DatabaseUsageLedger
from app.tools.registry import support_tool_definitions


class OpenAITextProvider:
    def __init__(
        self, *, client: Any, model: str, usage_ledger: DatabaseUsageLedger | None = None
    ) -> None:
        self._client = client
        self._model = model
        self._usage_ledger = usage_ledger

    async def generate_text(
        self,
        prompt: str,
        *,
        max_output_tokens: int = 300,
    ) -> GeneratedText:
        response = await self._client.responses.create(
            model=self._model,
            input=prompt,
            max_output_tokens=max_output_tokens,
            store=False,
        )
        usage = response.usage
        return GeneratedText(
            text=response.output_text,
            provider_request_id=response.id,
            input_tokens=usage.input_tokens if usage is not None else 0,
            output_tokens=usage.output_tokens if usage is not None else 0,
        )

    async def close(self) -> None:
        await self._client.close()

    async def choose_support_tool(
        self,
        query: str,
        *,
        history: Sequence[tuple[str, str]] = (),
        max_output_tokens: int = 80,
        operation_id: str | None = None,
    ) -> ToolDecisionResponse:
        payload = {
            "query": query.strip(),
            "recent_history": [{"role": role, "content": content} for role, content in history],
        }
        serialized = json.dumps(payload, ensure_ascii=False)
        if self._usage_ledger is not None:
            if not operation_id:
                raise ValueError("operation_id is required for a paid tool decision")
            await self._usage_ledger.reserve(
                operation_id=operation_id,
                provider="openai",
                model=self._model,
                estimated_input_tokens=max(1, len(serialized.encode("utf-8")) // 3),
                estimated_output_tokens=max_output_tokens,
                kind="chat",
            )
        try:
            response = await self._client.responses.create(
                model=self._model,
                instructions=(
                    "Choose at most one supplied read-only tool only when the user explicitly "
                    "asks for current service status, their open tickets, their recent ticket "
                    "history, or explicitly asks to draft a support ticket. Ticket creation is "
                    "only a proposal requiring "
                    "later approval. Otherwise do not call a tool. Never invent actor "
                    "identifiers or authorization fields."
                ),
                input=serialized,
                tools=support_tool_definitions(),
                tool_choice="auto",
                parallel_tool_calls=False,
                max_tool_calls=1,
                max_output_tokens=max_output_tokens,
                store=False,
            )
        except Exception:
            if self._usage_ledger is not None and operation_id:
                await self._usage_ledger.mark_unknown(operation_id=operation_id)
            raise
        raw_calls = [item for item in response.output if item.type == "function_call"]
        call: SupportToolCall | None = None
        contract_error: Exception | None = None
        if len(raw_calls) > 1:
            contract_error = ProviderContractError(
                "Provider returned more than one support tool call"
            )
        elif raw_calls:
            raw_call = raw_calls[0]
            try:
                arguments = json.loads(raw_call.arguments)
                call = SupportToolCall(
                    call_id=raw_call.call_id,
                    name=raw_call.name,
                    arguments=arguments,
                )
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                contract_error = error
        usage = response.usage
        input_tokens = usage.input_tokens if usage is not None else 0
        output_tokens = usage.output_tokens if usage is not None else 0
        if self._usage_ledger is not None and operation_id:
            await self._usage_ledger.complete(
                operation_id=operation_id,
                actual_input_tokens=input_tokens,
                actual_output_tokens=output_tokens,
                provider_request_id=response.id,
            )
        if contract_error is not None:
            raise ProviderContractError(
                "Provider returned an invalid support tool call"
            ) from contract_error
        return ToolDecisionResponse(
            call=call,
            provider_request_id=response.id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def generate_support_reply(
        self,
        query: str,
        *,
        evidence: list[EvidenceInput],
        history: Sequence[tuple[str, str]] = (),
        max_output_tokens: int = 400,
        operation_id: str | None = None,
    ) -> StructuredModelResponse:
        payload = {
            "query": query.strip(),
            "recent_history": [{"role": role, "content": content} for role, content in history],
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }
        serialized = json.dumps(payload, ensure_ascii=False)
        if self._usage_ledger is not None:
            if not operation_id:
                raise ValueError("operation_id is required for a paid structured call")
            estimated_input = max(1, len(serialized.encode("utf-8")) // 3)
            await self._usage_ledger.reserve(
                operation_id=operation_id,
                provider="openai",
                model=self._model,
                estimated_input_tokens=estimated_input,
                estimated_output_tokens=max_output_tokens,
                kind="chat",
            )
        try:
            response = await self._client.responses.parse(
                model=self._model,
                instructions=SUPPORT_INSTRUCTIONS,
                input=serialized,
                text_format=SupportReply,
                max_output_tokens=max_output_tokens,
                store=False,
            )
        except Exception:
            if self._usage_ledger is not None and operation_id:
                await self._usage_ledger.mark_unknown(operation_id=operation_id)
            raise
        parsed = response.output_parsed
        if parsed is None:
            raise ProviderContractError("OpenAI returned no parsed support reply")
        reply = validate_reply_sources(SupportReply.model_validate(parsed), evidence)
        usage = response.usage
        input_tokens = usage.input_tokens if usage is not None else 0
        output_tokens = usage.output_tokens if usage is not None else 0
        if self._usage_ledger is not None and operation_id:
            await self._usage_ledger.complete(
                operation_id=operation_id,
                actual_input_tokens=input_tokens,
                actual_output_tokens=output_tokens,
                provider_request_id=response.id,
            )
        return StructuredModelResponse(
            reply=reply,
            provider_request_id=response.id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


def build_openai_provider(
    *, api_key: str, model: str, usage_ledger: DatabaseUsageLedger | None = None
) -> OpenAITextProvider:
    client = AsyncOpenAI(api_key=api_key, max_retries=0, timeout=20.0)
    return OpenAITextProvider(client=client, model=model, usage_ledger=usage_ledger)
