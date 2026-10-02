from typing import Any, cast
from uuid import uuid4

from app.agent.context.builder import ContextMessage
from app.agent.context.schemas import SupportContext
from app.agent.openai_agents_runtime import (
    SupportAgentOutput,
    build_agents_input,
    guard_support_output,
)
from app.agent.request_policy import policy_for_request
from app.auth.principal import Principal
from app.db.models import UserRole


def _support_context(
    *,
    history: tuple[ContextMessage, ...],
    memories: tuple[ContextMessage, ...] = (),
) -> SupportContext:
    return SupportContext(
        principal=Principal(
            user_id=uuid4(),
            session_id=uuid4(),
            email="demo@example.com",
            display_name="Demo Administrator",
            role=UserRole.ADMIN,
            department_id=uuid4(),
            department_key="operations",
        ),
        conversation_id=uuid4(),
        query="Cách để truy cập VPN",
        history=history,
        memories=memories,
        device=None,
    )


def test_agents_input_preserves_roles_and_puts_current_request_last() -> None:
    support = _support_context(
        history=(
            ContextMessage(role="user", content="Tên tôi là gì?"),
            ContextMessage(role="assistant", content="Tên bạn là Demo Administrator."),
            ContextMessage(role="user", content="VPN đang hoạt động không?"),
            ContextMessage(role="assistant", content="VPN đang hoạt động bình thường."),
        ),
        memories=(ContextMessage(role="memory", content="operating_system=Ubuntu 24.04"),),
    )

    items = build_agents_input(support, "Cách để truy cập VPN")
    messages = [cast(dict[str, Any], item) for item in items]

    assert [(item["role"], item["content"]) for item in messages[:4]] == [
        ("user", "Tên tôi là gì?"),
        ("assistant", "Tên bạn là Demo Administrator."),
        ("user", "VPN đang hoạt động không?"),
        ("assistant", "VPN đang hoạt động bình thường."),
    ]
    assert messages[-2]["role"] == "user"
    assert "<confirmed_memory" in messages[-2]["content"]
    assert messages[-1] == {"role": "user", "content": "Cách để truy cập VPN"}


def test_agents_input_compacts_old_history_without_losing_latest_request() -> None:
    history = tuple(
        ContextMessage(
            role="user" if index % 2 == 0 else "assistant",
            content=f"Old topic {index}",
        )
        for index in range(24)
    )
    support = _support_context(history=history)

    items = build_agents_input(support, "Cách cấu hình Docker Registry của công ty?")
    messages = [cast(dict[str, Any], item) for item in items]

    assert "<older_conversation_summary" in messages[0]["content"]
    assert messages[-1] == {
        "role": "user",
        "content": "Cách cấu hình Docker Registry của công ty?",
    }
    assert len(items) < len(history) + 2


def test_request_policy_requires_knowledge_for_internal_guidance() -> None:
    policy = policy_for_request("Cách để truy cập VPN")

    assert policy.requires_knowledge is True
    assert policy.allows("search_knowledge_base") is True
    assert policy.allows("get_conversation_device") is True
    assert policy.allows("get_my_profile") is False
    assert policy.allows("check_service_status") is False
    assert policy_for_request("Xin chào, cách để truy cập VPN?").requires_knowledge is True


def test_request_policy_keeps_operational_reads_narrow() -> None:
    profile = policy_for_request("Tên tôi là gì?")
    service = policy_for_request("VPN đang hoạt động không?")
    ticket = policy_for_request("Tạo ticket VPN giúp tôi")

    assert profile.requires_knowledge is False
    assert profile.allowed_tools == frozenset({"get_my_profile"})
    assert service.requires_knowledge is False
    assert service.allowed_tools == frozenset({"check_service_status"})
    assert ticket.requires_knowledge is False
    assert ticket.allowed_tools == frozenset({"create_ticket", "get_conversation_device"})


def test_request_policy_treats_self_introduction_as_social_without_hiding_it_request() -> None:
    introduction = policy_for_request("Xin chào tôi tên là Lập")
    introduction_with_support = policy_for_request(
        "Xin chào, tôi tên là Lập và cách để truy cập VPN là gì?"
    )

    assert introduction.requires_knowledge is False
    assert introduction.allowed_tools == frozenset()
    assert introduction_with_support.requires_knowledge is True
    assert introduction_with_support.allows("search_knowledge_base") is True


def test_request_policy_does_not_force_knowledge_for_personal_conversation() -> None:
    full_name_statement = policy_for_request("Tên đầy đủ của tôi là Vũ Trung Lập")
    surname_follow_up = policy_for_request("Họ của tôi là gì?")
    middle_name_follow_up = policy_for_request("Tên đệm của tôi là gì?")

    assert full_name_statement.requires_knowledge is False
    assert full_name_statement.allowed_tools == frozenset()
    assert surname_follow_up.requires_knowledge is False
    assert surname_follow_up.allowed_tools == frozenset({"get_my_profile"})
    assert middle_name_follow_up.requires_knowledge is False
    assert middle_name_follow_up.allowed_tools == frozenset({"get_my_profile"})


def test_request_policy_allows_evidence_and_service_for_incident() -> None:
    policy = policy_for_request("Tôi không kết nối được VPN")

    assert policy.requires_knowledge is True
    assert policy.allowed_tools == frozenset(
        {
            "search_knowledge_base",
            "get_conversation_device",
            "check_service_status",
        }
    )


def test_output_guard_blocks_unsupported_internal_answer() -> None:
    guarded = guard_support_output(
        SupportAgentOutput(
            outcome="answered",
            answer="Hãy cài một VPN client bất kỳ.",
            citations=[],
        ),
        policy=policy_for_request("Cách để truy cập VPN"),
        retrieval_calls=1,
    )

    assert guarded.outcome == "no_answer"
    assert guarded.citations == []
    assert "Không tìm thấy tài liệu nội bộ" in guarded.answer


def test_output_guard_requires_a_clarifying_question() -> None:
    guarded = guard_support_output(
        SupportAgentOutput(
            outcome="needs_information",
            answer="Vui lòng cung cấp thêm thông tin.",
            citations=[],
        ),
        policy=policy_for_request("Cách để truy cập VPN"),
        retrieval_calls=1,
    )

    assert guarded.outcome == "needs_information"
    assert guarded.answer.endswith("?")
