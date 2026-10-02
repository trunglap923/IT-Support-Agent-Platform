from typing import Any, cast
from uuid import uuid4

from app.agent.context.builder import ContextMessage
from app.agent.context.schemas import SupportContext
from app.agent.openai_agents_runtime import build_agents_input
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
