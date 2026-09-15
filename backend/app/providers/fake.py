"""Deterministic offline provider for development and tests."""

from app.providers.base import GeneratedText


class FakeTextProvider:
    def __init__(self, response_text: str = "Phản hồi mô phỏng.") -> None:
        self._response_text = response_text

    async def generate_text(
        self,
        prompt: str,
        *,
        max_output_tokens: int = 300,
    ) -> GeneratedText:
        del prompt, max_output_tokens
        return GeneratedText(
            text=self._response_text,
            provider_request_id="fake-response",
            input_tokens=0,
            output_tokens=0,
        )

    async def close(self) -> None:
        return None
