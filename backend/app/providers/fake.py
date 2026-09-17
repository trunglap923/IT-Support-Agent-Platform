"""Deterministic offline provider for development and tests."""

import hashlib
from collections.abc import Sequence

from app.providers.base import GeneratedText
from app.providers.structured import (
    EvidenceInput,
    StructuredModelResponse,
    SupportReply,
    SupportToolCall,
    ToolDecisionResponse,
)


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

    async def choose_support_tool(
        self,
        query: str,
        *,
        history: Sequence[tuple[str, str]] = (),
        max_output_tokens: int = 80,
        operation_id: str | None = None,
    ) -> ToolDecisionResponse:
        del history, max_output_tokens, operation_id
        normalized = " ".join(query.casefold().split())
        call: SupportToolCall | None = None
        ticket_phrases = ("ticket của tôi", "ticket đang mở", "my open ticket", "my tickets")
        status_phrases = (
            "trạng thái",
            "dịch vụ có lỗi",
            "dịch vụ đang lỗi",
            "service status",
            "is down",
            "outage",
        )
        create_phrases = ("tạo ticket", "mở ticket", "create a ticket", "open a ticket")
        if any(phrase in normalized for phrase in create_phrases):
            issue_type = next(
                (item for item in ("vpn", "gitlab", "docker") if item in normalized),
                "other",
            )
            title = (
                f"Yêu cầu hỗ trợ {issue_type.upper()}"
                if issue_type != "other"
                else "Yêu cầu hỗ trợ IT"
            )
            call = SupportToolCall(
                call_id=self._fake_call_id(normalized),
                name="create_ticket",
                arguments={
                    "title": title,
                    "description": query.strip(),
                    "issue_type": issue_type,
                    "severity": "normal",
                    "device_id": None,
                },
            )
        elif any(phrase in normalized for phrase in ticket_phrases):
            call = SupportToolCall(
                call_id=self._fake_call_id(normalized),
                name="get_my_open_tickets",
                arguments={},
            )
        elif any(phrase in normalized for phrase in status_phrases):
            aliases = {
                "vpn": "vpn",
                "registry": "registry",
                "docker registry": "registry",
                "gitlab": "gitlab",
            }
            service_id = next(
                (value for alias, value in aliases.items() if alias in normalized), None
            )
            if service_id is not None:
                call = SupportToolCall(
                    call_id=self._fake_call_id(normalized),
                    name="check_service_status",
                    arguments={"service_id": service_id},
                )
        return ToolDecisionResponse(
            call=call,
            provider_request_id="fake-tool-decision",
            input_tokens=0,
            output_tokens=0,
        )

    @staticmethod
    def _fake_call_id(normalized_query: str) -> str:
        digest = hashlib.sha256(normalized_query.encode()).hexdigest()[:16]
        return f"fake-call-{digest}"

    async def generate_support_reply(
        self,
        query: str,
        *,
        evidence: list[EvidenceInput],
        history: Sequence[tuple[str, str]] = (),
        max_output_tokens: int = 400,
        operation_id: str | None = None,
    ) -> StructuredModelResponse:
        del query, history, max_output_tokens, operation_id
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
