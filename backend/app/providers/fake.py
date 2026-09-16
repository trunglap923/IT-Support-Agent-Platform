"""Deterministic offline provider for development and tests."""

from collections.abc import Sequence

from app.providers.base import GeneratedText
from app.providers.structured import EvidenceInput, StructuredModelResponse, SupportReply


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

    async def generate_support_reply(
        self,
        query: str,
        *,
        evidence: list[EvidenceInput],
        history: Sequence[tuple[str, str]] = (),
        max_output_tokens: int = 400,
    ) -> StructuredModelResponse:
        del query, history, max_output_tokens
        if not evidence:
            reply = SupportReply(
                outcome="no_answer",
                answer="Tôi chưa tìm thấy tài liệu nội bộ đủ căn cứ để trả lời câu hỏi này.",
                citations=[],
            )
        else:
            selected = evidence[:3]
            reply = SupportReply(
                outcome="answered",
                answer=" ".join(item.excerpt for item in selected),
                citations=[item.source_id for item in selected],
            )
        return StructuredModelResponse(
            reply=reply,
            provider_request_id="fake-structured-response",
            input_tokens=0,
            output_tokens=0,
        )
