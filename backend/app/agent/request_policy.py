"""Deterministic request policy for model-visible support tools and evidence."""

from __future__ import annotations

from dataclasses import dataclass

_ALL_TOOLS = frozenset(
    {
        "search_knowledge_base",
        "get_my_profile",
        "get_conversation_device",
        "check_service_status",
        "get_my_open_tickets",
        "get_my_recent_tickets",
        "create_ticket",
    }
)

_INCIDENT_MARKERS = (
    "không kết nối",
    "khong ket noi",
    "không truy cập",
    "khong truy cap",
    "không đăng nhập",
    "khong dang nhap",
    "bị lỗi",
    "bi loi",
    "lỗi ",
    "loi ",
    "error",
    "failed",
    "failure",
    "cannot",
    "can't",
    "timeout",
    "certificate",
)
_SERVICE_MARKERS = (
    "trạng thái",
    "trang thai",
    "hoạt động không",
    "hoat dong khong",
    "đang hoạt động",
    "dang hoat dong",
    "service status",
    "healthy",
    "outage",
    "down không",
)
_IDENTITY_MARKERS = (
    "tên tôi",
    "ten toi",
    "tôi là ai",
    "toi la ai",
    "who am i",
    "my name",
    "tài khoản của tôi",
    "tai khoan cua toi",
)
_TICKET_READ_MARKERS = (
    "ticket của tôi",
    "ticket cua toi",
    "ticket đang mở",
    "ticket dang mo",
    "ticket gần đây",
    "ticket gan day",
    "my tickets",
    "open tickets",
    "recent tickets",
    "liệt kê ticket",
    "liet ke ticket",
    "xem ticket",
)
_TICKET_CREATE_MARKERS = (
    "tạo ticket",
    "tao ticket",
    "mở ticket",
    "mo ticket",
    "draft ticket",
    "create ticket",
    "submit ticket",
)
_CONVERSATIONAL_REQUESTS = frozenset(
    {
        "xin chào",
        "xin chao",
        "chào bạn",
        "chao ban",
        "hello",
        "hi",
        "cảm ơn",
        "cảm ơn bạn",
        "cam on",
        "cam on ban",
        "thank you",
        "thanks",
        "tạm biệt",
        "tam biet",
        "goodbye",
    }
)
_MEMORY_MARKERS = (
    "ghi nhớ",
    "ghi nho",
    "hãy nhớ",
    "hay nho",
    "remember",
    "xóa memory",
    "xoa memory",
    "delete memory",
)


def _contains_any(query: str, markers: tuple[str, ...]) -> bool:
    return any(marker in query for marker in markers)


@dataclass(frozen=True, slots=True)
class AgentRequestPolicy:
    requires_knowledge: bool
    allowed_tools: frozenset[str]

    def allows(self, tool_name: str) -> bool:
        return tool_name in self.allowed_tools


def policy_for_request(query: str) -> AgentRequestPolicy:
    normalized = " ".join(query.casefold().split())
    has_incident = _contains_any(normalized, _INCIDENT_MARKERS)
    asks_service = _contains_any(normalized, _SERVICE_MARKERS)
    asks_identity = _contains_any(normalized, _IDENTITY_MARKERS)
    asks_ticket_read = _contains_any(normalized, _TICKET_READ_MARKERS)
    asks_ticket_create = _contains_any(normalized, _TICKET_CREATE_MARKERS)
    is_conversational = normalized.strip(" .!?") in _CONVERSATIONAL_REQUESTS
    is_memory_request = _contains_any(normalized, _MEMORY_MARKERS)

    requires_knowledge = (
        not asks_identity
        and not asks_service
        and not asks_ticket_read
        and not asks_ticket_create
        and not is_conversational
        and not is_memory_request
        and bool(normalized)
    )
    allowed: set[str] = set()
    if requires_knowledge:
        allowed.add("search_knowledge_base")
        allowed.add("get_conversation_device")
    if asks_identity:
        allowed.add("get_my_profile")
    if asks_service or has_incident:
        allowed.add("check_service_status")
    if asks_ticket_read:
        allowed.update({"get_my_open_tickets", "get_my_recent_tickets"})
    if asks_ticket_create:
        allowed.update({"create_ticket", "get_conversation_device"})

    return AgentRequestPolicy(
        requires_knowledge=requires_knowledge,
        allowed_tools=frozenset(allowed) & _ALL_TOOLS,
    )
