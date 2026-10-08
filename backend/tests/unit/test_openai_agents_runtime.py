import asyncio
from typing import Any, cast
from uuid import uuid4

from agents.run import RunContextWrapper

from app.agent.context.builder import ContextMessage
from app.agent.context.contracts import (
    ActiveContext,
    ActiveContextMessage,
    ContextTokenBudget,
)
from app.agent.context.schemas import SupportContext
from app.agent.openai_agents_runtime import (
    SupportAgentOutput,
    SupportRunHooks,
    SupportSDKContext,
    build_agents_input,
    guard_support_output,
)
from app.agent.request_policy import policy_for_request, resolve_request_policy
from app.auth.principal import Principal
from app.db.models import UserRole
from app.providers.structured import QueryAnalysisOutput, QueryAnalysisResponse


def _support_context(
    *,
    history: tuple[ContextMessage, ...],
    memories: tuple[ContextMessage, ...] = (),
    query: str = "Cách để truy cập VPN",
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
        query=query,
        history=history,
        memories=memories,
        device=None,
    )


def test_agents_input_preserves_roles_and_puts_current_request_last() -> None:
    support = _support_context(
        history=(
            ContextMessage(role="user", content="Tôi không truy cập được VPN trên Ubuntu."),
            ContextMessage(role="assistant", content="Bạn hãy kiểm tra VPN client trên Ubuntu."),
            ContextMessage(role="user", content="VPN đó vẫn báo lỗi timeout."),
            ContextMessage(role="assistant", content="Hãy thử kết nối lại VPN."),
        ),
        memories=(ContextMessage(role="memory", content="operating_system=Ubuntu 24.04"),),
        query="VPN đó vẫn chưa truy cập được?",
    )

    items = build_agents_input(support, support.query)
    messages = [cast(dict[str, Any], item) for item in items]

    roles_by_content = {item["content"]: item["role"] for item in messages}
    assert roles_by_content["Tôi không truy cập được VPN trên Ubuntu."] == "user"
    assert roles_by_content["Bạn hãy kiểm tra VPN client trên Ubuntu."] == "assistant"
    assert roles_by_content["VPN đó vẫn báo lỗi timeout."] == "user"
    assert roles_by_content["Hãy thử kết nối lại VPN."] == "assistant"
    assert not any('<context_item kind="semantic_memory"' in item["content"] for item in messages)
    assert messages[-1] == {"role": "user", "content": support.query}


def test_agents_input_drops_unrelated_old_history_without_losing_latest_request() -> None:
    history = tuple(
        ContextMessage(
            role="user" if index % 2 == 0 else "assistant",
            content=f"Old topic {index}",
        )
        for index in range(24)
    )
    support = _support_context(
        history=history,
        query="Cách cấu hình Docker Registry của công ty?",
    )

    items = build_agents_input(support, support.query)
    messages = [cast(dict[str, Any], item) for item in items]

    assert messages == [{"role": "user", "content": support.query}]


def test_context_refresh_retains_current_tool_call_and_output() -> None:
    """A refreshed context must still let the next model turn inspect the tool result."""

    support = _support_context(history=(), query="Tôi tên là gì?")

    class RefreshedContextBuilder:
        async def build(self, purpose: str, **kwargs: object) -> ActiveContext:
            del kwargs
            return ActiveContext(
                run_id=support.conversation_id,
                call_sequence=2,
                purpose=cast(Any, purpose),
                current_request=support.query,
                messages=(ActiveContextMessage(role="user", content=support.query),),
                selections=(),
                token_budget=ContextTokenBudget(
                    model_context_limit=16_000,
                    reserved_output_tokens=1_200,
                    safety_margin_tokens=1_600,
                    input_token_limit=11_220,
                ),
                estimated_input_tokens=8,
                bundle_hash="a" * 64,
                policy_version="test",
            )

    sdk_context = SupportSDKContext(
        support=support,
        executor=cast(Any, object()),
        database=cast(Any, object()),
        run_id=uuid4(),
        citation_store={},
        tool_calls=1,
        context_builder=cast(Any, RefreshedContextBuilder()),
    )
    input_items = cast(
        list[Any],
        [
            {"role": "user", "content": "stale seed input"},
            {
                "type": "function_call",
                "call_id": "call_profile",
                "name": "get_my_profile",
                "arguments": "{}",
            },
            {
                "type": "function_call_output",
                "call_id": "call_profile",
                "output": '{"ok":true,"display_name":"Demo Administrator"}',
            },
        ],
    )

    asyncio.run(
        SupportRunHooks().on_llm_start(
            RunContextWrapper(sdk_context),
            cast(Any, object()),
            None,
            input_items,
        )
    )

    assert input_items[0] == {"role": "user", "content": "Tôi tên là gì?"}
    assert [item["type"] for item in input_items[1:]] == [
        "function_call",
        "function_call_output",
    ]
    assert input_items[-1]["output"] == ('{"ok":true,"display_name":"Demo Administrator"}')


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


def test_low_confidence_request_uses_model_before_tool_policy() -> None:
    class KnowledgeModel:
        def __init__(self) -> None:
            self.calls = 0

        async def analyze_query(self, query: str, **kwargs: object) -> QueryAnalysisResponse:
            del query, kwargs
            self.calls += 1
            return QueryAnalysisResponse(
                analysis=QueryAnalysisOutput(
                    intent="knowledge",
                    semantic_query="internal onboarding portal",
                    exact_terms=["KB1234"],
                    products=["internal-portal"],
                    confidence=0.91,
                ),
                provider_request_id="query-analysis-1",
                input_tokens=12,
                output_tokens=7,
            )

    async def scenario() -> None:
        model = KnowledgeModel()
        policy = await resolve_request_policy(
            "Portal KB1234 dành cho máy mới",
            model=model,
            operation_id="test:query-analysis",
        )

        assert model.calls == 1
        assert policy.analysis.intent == "knowledge"
        assert policy.requires_knowledge is True
        assert policy.preferred_action == "knowledge"
        assert policy.allows("search_knowledge_base") is True
        assert policy.analysis.exact_terms == ("KB1234",)
        assert "KB1234" in policy.analysis.semantic_query
        assert policy.analysis_model_calls == 1
        assert policy.analysis_input_tokens == 12
        assert policy.analysis_output_tokens == 7

    asyncio.run(scenario())


def test_high_confidence_request_skips_model_analysis() -> None:
    class UnexpectedModel:
        async def analyze_query(self, query: str, **kwargs: object) -> QueryAnalysisResponse:
            del query, kwargs
            raise AssertionError("High-confidence requests must not call the model analyzer")

    policy = asyncio.run(
        resolve_request_policy(
            "Cách cấu hình VPN trên Ubuntu?",
            model=UnexpectedModel(),
            operation_id="test:query-analysis-skipped",
        )
    )

    assert policy.analysis.intent == "knowledge"
    assert policy.analysis.analyzer == "deterministic"
    assert policy.analysis_model_calls == 0


def test_low_confidence_model_failure_falls_back_to_deterministic_policy() -> None:
    class FailingModel:
        async def analyze_query(self, query: str, **kwargs: object) -> QueryAnalysisResponse:
            del query, kwargs
            raise RuntimeError("provider unavailable")

    policy = asyncio.run(
        resolve_request_policy(
            "Portal nội bộ dành cho máy mới",
            model=FailingModel(),
            operation_id="test:query-analysis-fallback",
        )
    )

    assert policy.analysis.intent == "unknown"
    assert policy.preferred_action == "direct"
    assert policy.analysis.analyzer == "deterministic"
    assert policy.analysis_model_calls == 1
    assert policy.analysis_input_tokens == 0
    assert policy.analysis_output_tokens == 0


def test_low_confidence_model_result_cannot_expand_tool_permissions() -> None:
    class UncertainModel:
        async def analyze_query(self, query: str, **kwargs: object) -> QueryAnalysisResponse:
            del query, kwargs
            return QueryAnalysisResponse(
                analysis=QueryAnalysisOutput(
                    intent="ticket_create",
                    semantic_query="create internal support ticket",
                    confidence=0.49,
                ),
                provider_request_id="uncertain-query-analysis",
                input_tokens=9,
                output_tokens=4,
            )

    policy = asyncio.run(
        resolve_request_policy(
            "Bạn xử lý giúp việc này",
            model=UncertainModel(),
            operation_id="test:uncertain-query-analysis",
        )
    )

    assert policy.analysis.intent == "unknown"
    assert policy.allowed_tools == frozenset()
    assert policy.analysis_model_calls == 1


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
