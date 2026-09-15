"""OpenAI Responses API adapter.

Tool calling and structured replies are added with the agent graph in WP-06.
"""

from typing import Any

from openai import AsyncOpenAI

from app.providers.base import GeneratedText


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


def build_openai_provider(*, api_key: str, model: str) -> OpenAITextProvider:
    client = AsyncOpenAI(api_key=api_key, max_retries=0, timeout=20.0)
    return OpenAITextProvider(client=client, model=model)
