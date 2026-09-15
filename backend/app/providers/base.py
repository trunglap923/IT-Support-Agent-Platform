"""Provider-neutral contracts used by orchestration code."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GeneratedText:
    text: str
    provider_request_id: str
    input_tokens: int
    output_tokens: int


class TextGenerationProvider(Protocol):
    async def generate_text(
        self,
        prompt: str,
        *,
        max_output_tokens: int = 300,
    ) -> GeneratedText:
        """Generate plain text without executing application tools."""

    async def close(self) -> None:
        """Release provider resources."""
