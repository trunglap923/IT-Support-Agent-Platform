"""OpenAI Responses API adapter."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI

from app.providers.base import GeneratedText
from app.providers.structured import (
    EvidenceInput,
    ProviderContractError,
    StructuredModelResponse,
    SupportReply,
    validate_reply_sources,
)

SUPPORT_INSTRUCTIONS = """You are an internal IT support assistant.
Answer only from the supplied evidence. Cite only source_id values supplied by the server.
If the evidence is insufficient, return outcome no_answer with no citations.
Keep the answer concise and do not invent procedures, links, or policy."""


class OpenAITextProvider:
    def __init__(self, *, client: Any, model: str) -> None:
        self._client = client
        self._model = model

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

    async def generate_support_reply(
        self,
        query: str,
        *,
        evidence: list[EvidenceInput],
        history: Sequence[tuple[str, str]] = (),
        max_output_tokens: int = 400,
    ) -> StructuredModelResponse:
        payload = {
            "query": query.strip(),
            "recent_history": [{"role": role, "content": content} for role, content in history],
            "evidence": [item.model_dump(mode="json") for item in evidence],
        }
        response = await self._client.responses.parse(
            model=self._model,
            instructions=SUPPORT_INSTRUCTIONS,
            input=json.dumps(payload, ensure_ascii=False),
            text_format=SupportReply,
            max_output_tokens=max_output_tokens,
            store=False,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ProviderContractError("OpenAI returned no parsed support reply")
        reply = validate_reply_sources(SupportReply.model_validate(parsed), evidence)
        usage = response.usage
        return StructuredModelResponse(
            reply=reply,
            provider_request_id=response.id,
            input_tokens=usage.input_tokens if usage is not None else 0,
            output_tokens=usage.output_tokens if usage is not None else 0,
        )


def build_openai_provider(*, api_key: str, model: str) -> OpenAITextProvider:
    client = AsyncOpenAI(api_key=api_key, max_retries=0, timeout=20.0)
    return OpenAITextProvider(client=client, model=model)
