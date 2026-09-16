"""Provider-neutral contracts used by orchestration code."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.providers.structured import EvidenceInput, StructuredModelResponse


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


class StructuredResponseProvider(TextGenerationProvider, Protocol):
    async def generate_support_reply(
        self,
        query: str,
        *,
        evidence: list[EvidenceInput],
        history: Sequence[tuple[str, str]] = (),
        max_output_tokens: int = 400,
    ) -> StructuredModelResponse:
        """Generate a validated support reply from server-controlled evidence."""
