"""OpenAI Responses API adapter."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.prompts import SUPPORT_INSTRUCTIONS
from app.providers.base import GeneratedText, TextDeltaCallback
from app.providers.structured import (
    EvidenceInput,
    IncompleteStructuredResponseError,
    InvalidStructuredResponseError,
    ProviderContractError,
    StructuredModelResponse,
    SupportReply,
    SupportToolCall,
    ToolDecisionResponse,
    validate_reply_sources,
)
from app.services.budget.service import DatabaseUsageLedger
from app.tools.registry import support_tool_definitions

_ANSWER_FIELD = re.compile(r'"answer"\s*:\s*"')
_SIMPLE_JSON_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


class _AnswerDeltaDecoder:
    """Extract decoded answer text from an incrementally streamed JSON object."""

    def __init__(self) -> None:
        self._raw = ""
        self._emitted_characters = 0

    def feed(self, raw_delta: str) -> str:
        self._raw += raw_delta
        decoded = self._decode_available_answer()
        delta = decoded[self._emitted_characters :]
        self._emitted_characters = len(decoded)
        return delta

    def _decode_available_answer(self) -> str:
        match = _ANSWER_FIELD.search(self._raw)
        if match is None:
            return ""
        index = match.end()
        decoded: list[str] = []
        while index < len(self._raw):
            character = self._raw[index]
            if character == '"':
                break
            if character != "\\":
                decoded.append(character)
                index += 1
                continue
            if index + 1 >= len(self._raw):
                break
            escape = self._raw[index + 1]
            if escape in _SIMPLE_JSON_ESCAPES:
                decoded.append(_SIMPLE_JSON_ESCAPES[escape])
                index += 2
                continue
            if escape != "u" or index + 6 > len(self._raw):
                break
            try:
                code_unit = int(self._raw[index + 2 : index + 6], 16)
            except ValueError:
                break
            if 0xD800 <= code_unit <= 0xDBFF:
                if index + 12 > len(self._raw) or self._raw[index + 6 : index + 8] != "\\u":
                    break
                try:
                    low_surrogate = int(self._raw[index + 8 : index + 12], 16)
                except ValueError:
                    break
                if not 0xDC00 <= low_surrogate <= 0xDFFF:
                    break
                code_point = 0x10000 + ((code_unit - 0xD800) << 10) + (low_surrogate - 0xDC00)
                decoded.append(chr(code_point))
                index += 12
                continue
            decoded.append(chr(code_unit))
            index += 6
        return "".join(decoded)


def _is_incomplete_json_validation(error: ValidationError) -> bool:
    for detail in error.errors(include_input=False):
        if detail.get("type") != "json_invalid":
            continue
        context = detail.get("ctx")
        if isinstance(context, dict) and str(context.get("error", "")).startswith(
            "EOF while parsing"
        ):
            return True
    return False


def _validation_summary(error: ValidationError) -> str:
    messages = [
        str(detail.get("msg", "invalid structured response"))
        for detail in error.errors(include_input=False)[:3]
    ]
    return "; ".join(messages)


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
                    "asks for their name or identity, current service status, their open tickets, "
                    "their recent ticket history, or explicitly asks to draft a support ticket. "
                    "Use get_my_profile for questions about the current user's name or identity. "
                    "Ticket creation is "
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
        max_output_tokens: int = 800,
        operation_id: str | None = None,
        on_text_delta: TextDeltaCallback | None = None,
        retry_instruction: str | None = None,
    ) -> StructuredModelResponse:
        payload: dict[str, Any] = {
            "query": query.strip(),
            "recent_history": [{"role": role, "content": content} for role, content in history],
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }
        if retry_instruction is not None:
            payload["retry_instruction"] = retry_instruction
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
        request = {
            "model": self._model,
            "instructions": SUPPORT_INSTRUCTIONS,
            "input": serialized,
            "text_format": SupportReply,
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
        try:
            if on_text_delta is None:
                response = await self._client.responses.parse(**request)
            else:
                decoder = _AnswerDeltaDecoder()
                async with self._client.responses.stream(**request) as stream:
                    async for event in stream:
                        if event.type != "response.output_text.delta":
                            continue
                        answer_delta = decoder.feed(event.delta)
                        if answer_delta:
                            await on_text_delta(answer_delta)
                    response = await stream.get_final_response()
        except Exception as error:
            if self._usage_ledger is not None and operation_id:
                await self._usage_ledger.mark_unknown(operation_id=operation_id)
            if isinstance(error, ValidationError) and _is_incomplete_json_validation(error):
                raise IncompleteStructuredResponseError(
                    "OpenAI stopped before completing the structured support reply"
                ) from None
            if isinstance(error, ValidationError):
                raise InvalidStructuredResponseError(
                    "OpenAI returned a support reply that violates the application contract: "
                    f"{_validation_summary(error)}"
                ) from error
            raise
        if getattr(response, "status", None) == "incomplete":
            if self._usage_ledger is not None and operation_id:
                await self._usage_ledger.mark_unknown(operation_id=operation_id)
            raise IncompleteStructuredResponseError(
                "OpenAI stopped before completing the structured support reply"
            )
        parsed = response.output_parsed
        if parsed is None:
            if self._usage_ledger is not None and operation_id:
                await self._usage_ledger.mark_unknown(operation_id=operation_id)
            raise ProviderContractError("OpenAI returned no parsed support reply")
        try:
            reply = validate_reply_sources(SupportReply.model_validate(parsed), evidence)
        except ValidationError as error:
            if self._usage_ledger is not None and operation_id:
                await self._usage_ledger.mark_unknown(operation_id=operation_id)
            raise InvalidStructuredResponseError(
                "OpenAI returned a support reply that violates the application contract: "
                f"{_validation_summary(error)}"
            ) from error
        except ProviderContractError:
            if self._usage_ledger is not None and operation_id:
                await self._usage_ledger.mark_unknown(operation_id=operation_id)
            raise
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
