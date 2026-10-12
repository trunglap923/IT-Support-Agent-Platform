"""Deterministic offline provider for development and tests."""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.providers.base import GeneratedText, TextDeltaCallback
from app.providers.structured import (
    EvidenceInput,
    ExecutionPlanResponse,
    QueryAnalysisOutput,
    QueryAnalysisResponse,
    StructuredModelResponse,
    SupportExecutionPlan,
    SupportReply,
    SupportToolCall,
    ToolDecisionResponse,
)

_VIETNAMESE_CHARACTERS = frozenset(
    "ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
)
_VIETNAMESE_MARKERS = frozenset(
    {
        "ban",
        "cach",
        "duoc",
        "giup",
        "khong",
        "lam",
        "muon",
        "nao",
        "thai",
        "the",
        "toi",
        "trang",
    }
)
_MARKDOWN_HEADING = re.compile(r"(^|\s)#{1,6}\s+")
_WHITESPACE = re.compile(r"\s+")
_TICKET_EDIT_FIELD = re.compile(
    r"^(Tiêu đề|Mô tả|Loại sự cố|Mức độ|Thiết bị):[ \t]*(.*?)"
    r"(?=^(?:Tiêu đề|Mô tả|Loại sự cố|Mức độ|Thiết bị):|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


@dataclass(slots=True)
class _EvidenceGroup:
    title: str
    excerpts: list[str]
    source_ids: list[str]
    fallback_source_id: str


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

    async def analyze_query(
        self,
        query: str,
        *,
        deterministic: object,
        history: Sequence[tuple[str, str]] = (),
        max_output_tokens: int = 180,
        operation_id: str | None = None,
    ) -> QueryAnalysisResponse:
        del history, max_output_tokens, operation_id
        filters = getattr(deterministic, "filters", None)
        analysis = QueryAnalysisOutput(
            intent=getattr(deterministic, "intent", "unknown"),
            semantic_query=getattr(deterministic, "semantic_query", query.strip()),
            exact_terms=list(getattr(deterministic, "exact_terms", ())),
            services=list(getattr(filters, "services", ())),
            products=list(getattr(filters, "products", ())),
            operating_systems=list(getattr(filters, "operating_systems", ())),
            error_codes=list(getattr(filters, "error_codes", ())),
            versions=list(getattr(filters, "version_labels", ())),
            version_scope=getattr(filters, "version_scope", "current"),
            confidence=getattr(deterministic, "confidence", 0.0),
        )
        return QueryAnalysisResponse(
            analysis=analysis,
            provider_request_id="fake-query-analysis",
            input_tokens=0,
            output_tokens=0,
        )

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
        recent_ticket_phrases = (
            "ticket gần đây",
            "lịch sử ticket",
            "ticket của tôi",
            "recent ticket",
            "ticket history",
            "my tickets",
        )
        open_ticket_phrases = ("ticket đang mở", "open ticket", "active ticket")
        status_phrases = (
            "trạng thái",
            "dịch vụ có lỗi",
            "dịch vụ đang lỗi",
            "service status",
            "is down",
            "outage",
        )
        create_phrases = ("tạo ticket", "mở ticket", "create a ticket", "open a ticket")
        profile_phrases = (
            "tôi tên là gì",
            "tên của tôi",
            "tôi là ai",
            "what is my name",
            "who am i",
        )
        if any(phrase in normalized for phrase in profile_phrases):
            call = SupportToolCall(
                call_id=self._fake_call_id(normalized),
                name="get_my_profile",
                arguments={},
            )
        elif any(phrase in normalized for phrase in create_phrases):
            fields = self._ticket_edit_fields(query)
            requested_issue_type = fields.get("loại sự cố", "").casefold()
            issue_type = (
                requested_issue_type
                if requested_issue_type in {"vpn", "gitlab", "docker", "other"}
                else next(
                    (item for item in ("vpn", "gitlab", "docker") if item in normalized),
                    "other",
                )
            )
            default_title = (
                f"Yêu cầu hỗ trợ {issue_type.upper()}"
                if issue_type != "other"
                else "Yêu cầu hỗ trợ IT"
            )
            severity = fields.get("mức độ", "normal").casefold()
            if severity not in {"low", "normal", "high"}:
                severity = "normal"
            call = SupportToolCall(
                call_id=self._fake_call_id(normalized),
                name="create_ticket",
                arguments={
                    "title": fields.get("tiêu đề", default_title),
                    "description": fields.get("mô tả", query.strip()),
                    "issue_type": issue_type,
                    "severity": severity,
                    "device_id": fields.get("thiết bị"),
                },
            )
        elif any(phrase in normalized for phrase in open_ticket_phrases):
            call = SupportToolCall(
                call_id=self._fake_call_id(normalized),
                name="get_my_open_tickets",
                arguments={},
            )
        elif any(phrase in normalized for phrase in recent_ticket_phrases):
            call = SupportToolCall(
                call_id=self._fake_call_id(normalized),
                name="get_my_recent_tickets",
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

    async def plan_support_steps(
        self,
        query: str,
        *,
        selected_action: str,
        history: Sequence[tuple[str, str]] = (),
        max_output_tokens: int = 120,
        operation_id: str | None = None,
    ) -> ExecutionPlanResponse:
        del max_output_tokens, operation_id
        normalized = " ".join(query.casefold().split())
        steps: list[str] = []
        tool_arguments: dict[str, object] = {}
        if selected_action == "auto":
            decision = await self.choose_support_tool(query, history=history)
            if decision.call is not None:
                selected_action = decision.call.name
                tool_arguments = decision.call.arguments
            else:
                direct_phrases = (
                    "xin chào",
                    "chào bạn",
                    "hello",
                    "hi ",
                    "cảm ơn",
                    "thank",
                )
                selected_action = (
                    "direct"
                    if normalized in {"hi", "hello"}
                    or any(phrase in normalized for phrase in direct_phrases)
                    else "knowledge"
                )
        elif selected_action != "direct":
            decision = await self.choose_support_tool(query, history=history)
            if decision.call is not None and decision.call.name == selected_action:
                tool_arguments = decision.call.arguments
        device_markers = ("ubuntu", "windows", "macos", "laptop", "máy", "thiết bị")
        if selected_action in {"knowledge", "check_service_status"} and any(
            marker in normalized for marker in device_markers
        ):
            steps.append("device")
        action_stage = {
            "knowledge": "knowledge",
            "direct": "answer",
            "get_my_profile": "profile",
            "check_service_status": "service",
            "get_my_open_tickets": "support_data",
            "get_my_recent_tickets": "support_data",
            "create_ticket": "approval",
        }.get(selected_action, "knowledge")
        steps.append(action_stage)
        if action_stage not in {"approval", "answer"}:
            steps.append("answer")
        plan_data: dict[str, object] = {"action": selected_action, "steps": steps}
        if selected_action == "check_service_status":
            plan_data["service_id"] = tool_arguments.get("service_id")
        if selected_action == "create_ticket":
            plan_data.update(
                {
                    "ticket_title": tool_arguments.get("title"),
                    "ticket_description": tool_arguments.get("description"),
                    "ticket_issue_type": tool_arguments.get("issue_type"),
                    "ticket_severity": tool_arguments.get("severity"),
                    "ticket_device_id": tool_arguments.get("device_id"),
                }
            )
        return ExecutionPlanResponse(
            plan=SupportExecutionPlan.model_validate(plan_data),
            provider_request_id="fake-execution-plan",
            input_tokens=0,
            output_tokens=0,
        )

    @staticmethod
    def _fake_call_id(normalized_query: str) -> str:
        digest = hashlib.sha256(normalized_query.encode()).hexdigest()[:16]
        return f"fake-call-{digest}"

    @staticmethod
    def _uses_vietnamese(query: str) -> bool:
        normalized = query.casefold()
        if any(character in _VIETNAMESE_CHARACTERS for character in normalized):
            return True
        words = set(re.findall(r"\w+", normalized))
        return len(words & _VIETNAMESE_MARKERS) >= 2

    @staticmethod
    def _ticket_edit_fields(query: str) -> dict[str, str]:
        return {
            label.casefold(): value.strip()
            for label, value in _TICKET_EDIT_FIELD.findall(query)
            if value.strip()
        }

    @staticmethod
    def _plain_evidence(excerpt: str) -> str:
        without_headings = _MARKDOWN_HEADING.sub(r"\1", excerpt)
        return _WHITESPACE.sub(" ", without_headings).strip()

    @classmethod
    def _format_evidence_summary(
        cls,
        evidence: Sequence[EvidenceInput],
        *,
        vietnamese: bool,
    ) -> tuple[str, list[str]]:
        if vietnamese:
            introduction = (
                "Tôi đã tìm thấy hướng dẫn nội bộ liên quan. Nội dung tài liệu được giữ "
                "nguyên để tránh làm sai lệch hướng dẫn:"
            )
        else:
            introduction = "I found relevant internal guidance. Follow the documented steps below:"
        groups: dict[str, _EvidenceGroup] = {}
        for item in evidence:
            title = _WHITESPACE.sub(" ", item.title).strip()
            title_key = title.casefold()
            group = groups.setdefault(
                title_key,
                _EvidenceGroup(
                    title=title,
                    excerpts=[],
                    source_ids=[],
                    fallback_source_id=item.source_id,
                ),
            )
            excerpt = cls._plain_evidence(item.excerpt)
            excerpt_key = excerpt.casefold()
            existing_excerpts = {value.casefold() for value in group.excerpts}
            if excerpt and excerpt_key != title_key and excerpt_key not in existing_excerpts:
                group.excerpts.append(excerpt)
                group.source_ids.append(item.source_id)

        items: list[str] = []
        citations: list[str] = []
        for index, group in enumerate(groups.values(), start=1):
            lines = [f"{index}. {group.title}"]
            if len(group.excerpts) == 1:
                lines.append(f"   {group.excerpts[0]}")
            else:
                lines.extend(f"   - {excerpt}" for excerpt in group.excerpts)
            items.append("\n".join(lines))
            citations.extend(group.source_ids or [group.fallback_source_id])

        answer = f"{introduction}\n\n" + "\n\n".join(items)
        return answer, citations

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
        allow_conversation_transform: bool = False,
    ) -> StructuredModelResponse:
        del max_output_tokens, operation_id, retry_instruction
        vietnamese = self._uses_vietnamese(query)
        previous_answer = next(
            (content.strip() for role, content in reversed(history) if role == "assistant"),
            "",
        )
        if allow_conversation_transform and previous_answer:
            reply = SupportReply(
                outcome="answered",
                answer=previous_answer,
                citations=[],
                answer_basis="conversation_transform",
            )
        elif not evidence:
            reply = SupportReply(
                outcome="no_answer",
                answer=(
                    "Tôi chưa tìm thấy tài liệu nội bộ đủ căn cứ để trả lời câu hỏi này. "
                    "Vui lòng liên hệ IT để được hỗ trợ."
                    if vietnamese
                    else "I couldn't find sufficient internal documentation to answer this "
                    "question. Please contact IT for support."
                ),
                citations=[],
            )
        else:
            selected = evidence[:3]
            answer, citations = self._format_evidence_summary(
                selected,
                vietnamese=vietnamese,
            )
            reply = SupportReply(
                outcome="answered",
                answer=answer,
                citations=citations,
            )
        if on_text_delta is not None:
            for delta in re.findall(r"\S+\s*|\s+", reply.answer):
                await on_text_delta(delta)
        return StructuredModelResponse(
            reply=reply,
            provider_request_id="fake-structured-response",
            input_tokens=0,
            output_tokens=0,
        )
