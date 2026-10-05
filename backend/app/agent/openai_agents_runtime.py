"""OpenAI Agents SDK runtime for bounded, tool-using IT support turns."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID, uuid4

from agents import Agent, ModelSettings, RunConfig, Runner, function_tool
from agents.items import TResponseInputItem
from agents.lifecycle import RunHooksBase
from agents.models.openai_provider import OpenAIProvider
from agents.run import RunContextWrapper
from agents.run_state import RunState
from openai import AsyncOpenAI
from pydantic import BaseModel, ConfigDict, Field

from app.agent.context.builder import build_agent_context
from app.agent.context.schemas import SupportContext
from app.agent.request_policy import AgentRequestPolicy, policy_for_request
from app.agent.runtime import AgentRuntimeResult
from app.db import Database
from app.prompts import SUPPORT_INSTRUCTIONS
from app.providers.base import TextDeltaCallback
from app.services.budget.service import DatabaseUsageLedger
from app.services.tickets import TicketWriteService
from app.tools.executor import ToolExecutor
from app.tools.registry import TOOL_REGISTRY
from app.tools.schemas import CreateTicketArguments

ProgressCallback = Callable[[str, str, str | None, int | None], Awaitable[None]]
StreamStartedCallback = Callable[[], Awaitable[None]]

MAX_AGENT_TURNS = 6
MAX_READ_TOOL_CALLS = 4


class SupportAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: str = Field(pattern="^(answered|no_answer|needs_information)$")
    answer: str = Field(min_length=1, max_length=4_000)
    citations: list[str] = Field(default_factory=list, max_length=5)


def guard_support_output(
    output: SupportAgentOutput,
    *,
    policy: AgentRequestPolicy,
    retrieval_calls: int,
) -> SupportAgentOutput:
    """Apply application-owned evidence and outcome invariants to final model output."""

    if policy.requires_knowledge and retrieval_calls == 0:
        return SupportAgentOutput(
            outcome="no_answer",
            answer=(
                "Tôi chưa thể tra cứu kho tri thức nội bộ cho yêu cầu này, nên chưa có đủ "
                "căn cứ để hướng dẫn. Vui lòng thử lại hoặc liên hệ IT."
            ),
            citations=[],
        )
    if policy.requires_knowledge and output.outcome == "answered" and not output.citations:
        return SupportAgentOutput(
            outcome="no_answer",
            answer=(
                "Không tìm thấy tài liệu nội bộ đủ căn cứ để trả lời yêu cầu này. "
                "Vui lòng cung cấp thêm chi tiết hoặc liên hệ IT."
            ),
            citations=[],
        )
    if output.outcome == "needs_information" and "?" not in output.answer:
        return SupportAgentOutput(
            outcome="needs_information",
            answer=(
                "Mình cần thêm thông tin để trả lời chính xác. Bạn có thể cung cấp chi tiết "
                "còn thiếu về yêu cầu hiện tại không?"
            ),
            citations=[],
        )
    if output.outcome == "no_answer" and output.citations:
        return output.model_copy(update={"citations": []})
    return output


def build_agents_input(
    support: SupportContext,
    query: str,
) -> list[TResponseInputItem]:
    """Build bounded Responses input with the current request as the final user turn."""

    context = build_agent_context(
        current_query=query,
        history=support.model_history,
    )
    items: list[TResponseInputItem] = []
    if context.conversation_summary:
        items.append(
            {
                "role": "user",
                "content": (
                    '<older_conversation_summary context_only="true">\n'
                    f"{context.conversation_summary}\n"
                    "</older_conversation_summary>"
                ),
            }
        )
    for message in context.history:
        if message.role == "memory":
            items.append(
                {
                    "role": "user",
                    "content": (
                        '<confirmed_memory context_only="true">\n'
                        f"{message.content}\n"
                        "</confirmed_memory>"
                    ),
                }
            )
        else:
            items.append({"role": message.role, "content": message.content})
    if context.confirmed_attempted_steps:
        attempted = "\n".join(f"- {step}" for step in context.confirmed_attempted_steps)
        items.append(
            {
                "role": "user",
                "content": (
                    '<confirmed_attempted_steps context_only="true">\n'
                    f"{attempted}\n"
                    "</confirmed_attempted_steps>"
                ),
            }
        )
    items.append({"role": "user", "content": context.current_query})
    return items


@dataclass(slots=True)
class SupportSDKContext:
    support: SupportContext
    executor: ToolExecutor
    database: Database
    run_id: UUID
    citation_store: dict[str, dict[str, Any]]
    on_progress: ProgressCallback | None = None
    approval_id: UUID | None = None
    approval_decision: str | None = None
    tool_calls: int = 0
    retrieval_calls: int = 0
    ticket_display_key: str | None = None
    completed_stages: set[str] = field(default_factory=set)
    policy: AgentRequestPolicy | None = None

    @property
    def request_policy(self) -> AgentRequestPolicy:
        if self.policy is None:
            self.policy = policy_for_request(self.support.query)
        return self.policy

    async def progress(
        self,
        stage: str,
        status: str,
        detail: str | None = None,
        count: int | None = None,
    ) -> None:
        if self.on_progress is not None:
            await self.on_progress(stage, status, detail, count)

    async def execute(self, name: str, arguments: dict[str, Any]) -> str:
        if self.tool_calls >= MAX_READ_TOOL_CALLS:
            return json.dumps(
                {"ok": False, "error": {"code": "tool_call_limit"}},
                ensure_ascii=False,
            )
        self.tool_calls += 1
        if not self.request_policy.allows(name):
            return json.dumps(
                {"ok": False, "error": {"code": "tool_not_relevant_to_current_request"}},
                ensure_ascii=False,
            )
        if name == "search_knowledge_base":
            self.retrieval_calls += 1
        result = await self.executor.execute(
            call_id=f"sdk:{self.run_id}:{uuid4()}",
            name=name,
            arguments=arguments,
        )
        return result.model_dump_json()


def _tools() -> list[Any]:
    async def create_ticket_needs_approval(
        ctx: RunContextWrapper[SupportSDKContext],
        parameters: dict[str, Any],
        call_id: str,
    ) -> bool:
        del parameters, call_id
        if not ctx.context.request_policy.allows("create_ticket"):
            return False
        decision = ctx.context.executor.policy.evaluate(
            spec=TOOL_REGISTRY["create_ticket"],
            actor_role=ctx.context.executor.context.actor_role,
        )
        return decision.action == "approval"

    @function_tool(
        description_override="Read the current authenticated user's display name.",
        use_docstring_info=False,
    )
    async def get_my_profile(ctx: RunContextWrapper[SupportSDKContext]) -> str:
        return await ctx.context.execute("get_my_profile", {})

    @function_tool(
        description_override="Read the active device attached to this conversation.",
        use_docstring_info=False,
    )
    async def get_conversation_device(ctx: RunContextWrapper[SupportSDKContext]) -> str:
        context = ctx.context
        if context.tool_calls >= MAX_READ_TOOL_CALLS:
            return json.dumps({"ok": False, "error": {"code": "tool_call_limit"}})
        context.tool_calls += 1
        if not context.request_policy.allows("get_conversation_device"):
            return json.dumps(
                {"ok": False, "error": {"code": "tool_not_relevant_to_current_request"}},
                ensure_ascii=False,
            )
        device = context.support.device
        if device is None:
            return json.dumps({"ok": True, "device": None}, ensure_ascii=False)
        return json.dumps(
            {
                "ok": True,
                "device": {
                    "id": str(device.id),
                    "label": device.label,
                    "platform": device.platform,
                },
            },
            ensure_ascii=False,
        )

    @function_tool(
        description_override="Read the current health of VPN, Docker Registry, or GitLab.",
        use_docstring_info=False,
    )
    async def check_service_status(
        ctx: RunContextWrapper[SupportSDKContext],
        service_id: Literal["vpn", "registry", "gitlab"],
    ) -> str:
        return await ctx.context.execute(
            "check_service_status",
            {"service_id": service_id},
        )

    @function_tool(
        description_override="List at most ten open tickets owned by the current user.",
        use_docstring_info=False,
    )
    async def get_my_open_tickets(ctx: RunContextWrapper[SupportSDKContext]) -> str:
        return await ctx.context.execute("get_my_open_tickets", {})

    @function_tool(
        description_override="List at most ten recently updated tickets owned by the current user.",
        use_docstring_info=False,
    )
    async def get_my_recent_tickets(ctx: RunContextWrapper[SupportSDKContext]) -> str:
        return await ctx.context.execute("get_my_recent_tickets", {})

    @function_tool(
        description_override=(
            "Search approved internal IT documents. Use the returned source_id values in the "
            "final citations field."
        ),
        use_docstring_info=False,
    )
    async def search_knowledge_base(
        ctx: RunContextWrapper[SupportSDKContext], query: str, limit: int = 5
    ) -> str:
        return await ctx.context.execute(
            "search_knowledge_base",
            {"query": query, "limit": limit},
        )

    @function_tool(
        description_override=(
            "Create a support ticket after explicit human approval. Use only when the user "
            "explicitly asks to create or draft a ticket."
        ),
        use_docstring_info=False,
        needs_approval=create_ticket_needs_approval,
    )
    async def create_ticket(
        ctx: RunContextWrapper[SupportSDKContext],
        title: str,
        description: str,
        issue_type: Literal["vpn", "docker", "gitlab", "other"],
        severity: Literal["low", "normal", "high"] = "normal",
        device_id: str | None = None,
    ) -> str:
        context = ctx.context
        if not context.request_policy.allows("create_ticket"):
            return json.dumps(
                {"ok": False, "error": {"code": "tool_not_relevant_to_current_request"}},
                ensure_ascii=False,
            )
        policy_decision = context.executor.policy.evaluate(
            spec=TOOL_REGISTRY["create_ticket"],
            actor_role=context.executor.context.actor_role,
        )
        if policy_decision.action == "deny":
            return json.dumps(
                {"ok": False, "error": {"code": policy_decision.reason_code}},
                ensure_ascii=False,
            )
        arguments = CreateTicketArguments.model_validate(
            {
                "title": title,
                "description": description,
                "issue_type": issue_type,
                "severity": severity,
                "device_id": device_id,
            }
        )
        if context.approval_id is None or context.approval_decision != "approved":
            return json.dumps(
                {"ok": False, "error": {"code": "approval_not_available"}},
                ensure_ascii=False,
            )
        async with context.database.session() as session, session.begin():
            receipt = await TicketWriteService().create_from_approval(
                session,
                approval_id=context.approval_id,
                owner_id=context.support.principal.user_id,
            )
        context.tool_calls += 1
        context.ticket_display_key = receipt.display_key
        return json.dumps(
            {
                "ok": True,
                "ticket": {
                    "id": str(receipt.ticket_id),
                    "display_key": receipt.display_key,
                    "title": arguments.title,
                },
            },
            ensure_ascii=False,
        )

    return [
        get_my_profile,
        get_conversation_device,
        check_service_status,
        get_my_open_tickets,
        get_my_recent_tickets,
        search_knowledge_base,
        create_ticket,
    ]


_STAGE_BY_TOOL = {
    "get_my_profile": "profile",
    "get_conversation_device": "device",
    "check_service_status": "service",
    "get_my_open_tickets": "support_data",
    "get_my_recent_tickets": "support_data",
    "search_knowledge_base": "knowledge",
    "create_ticket": "approval",
}

_TOOL_PROGRESS = {
    "get_my_profile": ("Đang đọc thông tin tài khoản.", "Đã đọc thông tin tài khoản."),
    "get_conversation_device": ("Đang kiểm tra thiết bị liên quan.", "Đã kiểm tra thiết bị."),
    "check_service_status": ("Đang kiểm tra trạng thái dịch vụ.", "Đã kiểm tra dịch vụ."),
    "get_my_open_tickets": ("Đang đọc ticket đang mở.", "Đã đọc ticket đang mở."),
    "get_my_recent_tickets": ("Đang đọc ticket gần đây.", "Đã đọc ticket gần đây."),
    "search_knowledge_base": ("Đang tìm trong kho tri thức.", "Đã tìm xong tài liệu liên quan."),
    "create_ticket": ("Đang tạo ticket đã được duyệt.", "Đã hoàn tất tạo ticket."),
}


class SupportRunHooks(RunHooksBase[SupportSDKContext, Agent[SupportSDKContext]]):
    async def on_tool_start(
        self,
        context: RunContextWrapper[SupportSDKContext],
        agent: Agent[SupportSDKContext],
        tool: Any,
    ) -> None:
        del agent
        name = str(getattr(tool, "name", ""))
        stage = _STAGE_BY_TOOL.get(name, "support_data")
        started_detail = _TOOL_PROGRESS.get(name, ("Đang xử lý dữ liệu hỗ trợ.", ""))[0]
        await context.context.progress(stage, "started", started_detail)

    async def on_tool_end(
        self,
        context: RunContextWrapper[SupportSDKContext],
        agent: Agent[SupportSDKContext],
        tool: Any,
        result: object,
    ) -> None:
        del agent
        name = str(getattr(tool, "name", ""))
        stage = _STAGE_BY_TOOL.get(name, "support_data")
        event_status = "completed"
        completed_detail = _TOOL_PROGRESS.get(name, ("", "Đã xử lý dữ liệu hỗ trợ."))[1]
        if isinstance(result, str):
            try:
                payload = json.loads(result)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict) and (
                payload.get("status") in {"failed", "unknown"} or payload.get("ok") is False
            ):
                event_status = "warning"
                completed_detail = "Tool chưa trả về kết quả sử dụng được; Agent đang xử lý tiếp."
        if event_status == "completed":
            context.context.completed_stages.add(stage)
        await context.context.progress(stage, event_status, completed_detail)


class OpenAIAgentsRuntime:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        context: SupportSDKContext,
        operation_id: str,
        usage_ledger: DatabaseUsageLedger | None = None,
        on_stream_started: StreamStartedCallback | None = None,
        on_text_delta: TextDeltaCallback | None = None,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, max_retries=0, timeout=30.0)
        self._model_provider = OpenAIProvider(openai_client=self._client, use_responses=True)
        self._context = context
        self._operation_id = operation_id
        self._usage_ledger = usage_ledger
        self._on_stream_started = on_stream_started
        self._on_text_delta = on_text_delta
        self._request_policy = policy_for_request(context.support.query)
        self._context.policy = self._request_policy
        self._agent = Agent[SupportSDKContext](
            name="IT Support Orchestrator",
            instructions=SUPPORT_INSTRUCTIONS,
            model=model,
            model_settings=ModelSettings(
                parallel_tool_calls=False,
                # Let the model read the current request and choose its next action. The
                # request policy and output guard remain deterministic safety boundaries.
                tool_choice="auto",
                max_tokens=800,
                store=False,
            ),
            tools=_tools(),
            output_type=SupportAgentOutput,
        )

    def _input(self, query: str) -> list[TResponseInputItem]:
        return build_agents_input(self._context.support, query)

    async def _resume_state(self, serialized_state: str) -> RunState[Any, Agent[Any]]:
        state = await RunState.from_string(
            self._agent,
            serialized_state,
            context_override=RunContextWrapper(self._context),
            strict_context=True,
        )
        interruptions = state.get_interruptions()
        if len(interruptions) != 1:
            raise RuntimeError("Resumable agent state must contain exactly one approval")
        interruption = interruptions[0]
        if interruption.name != "create_ticket":
            raise RuntimeError("Resumable agent state contains an unexpected tool approval")
        if self._context.approval_decision == "approved":
            state.approve(interruption)
        elif self._context.approval_decision == "rejected":
            state.reject(
                interruption,
                rejection_message="Người dùng đã từ chối tạo ticket.",
            )
        else:
            raise RuntimeError("Approval decision is required to resume the agent")
        return state

    async def run(self, *, query: str, serialized_state: str | None = None) -> AgentRuntimeResult:
        prepared_input = self._input(query)
        estimated_input = max(
            1,
            len(json.dumps(prepared_input, ensure_ascii=False).encode("utf-8")) // 3,
        )
        if self._usage_ledger is not None:
            await self._usage_ledger.reserve(
                operation_id=self._operation_id,
                provider="openai",
                model=str(self._agent.model),
                estimated_input_tokens=estimated_input * MAX_AGENT_TURNS,
                estimated_output_tokens=800 * MAX_AGENT_TURNS,
                kind="agent",
            )
        if self._on_stream_started is not None:
            await self._on_stream_started()
        await self._context.progress("analyze", "completed", "Agent đã xác định bước tiếp theo.")
        agent_input: list[TResponseInputItem] | RunState[Any, Agent[Any]] = (
            await self._resume_state(serialized_state)
            if serialized_state is not None
            else prepared_input
        )
        try:
            streamed = Runner.run_streamed(
                self._agent,
                agent_input,
                context=None if serialized_state is not None else self._context,
                max_turns=MAX_AGENT_TURNS,
                hooks=SupportRunHooks(),
                run_config=RunConfig(
                    model_provider=self._model_provider,
                    workflow_name="IT Support",
                    group_id=str(self._context.support.conversation_id),
                    trace_metadata={"run_id": str(self._context.run_id)},
                    trace_include_sensitive_data=False,
                ),
            )
            async for _event in streamed.stream_events():
                pass
        except Exception:
            if self._usage_ledger is not None:
                await self._usage_ledger.mark_unknown(operation_id=self._operation_id)
            fallback_answer = None
            fallback_outcome = None
            if self._context.ticket_display_key is not None:
                fallback_answer = f"Ticket {self._context.ticket_display_key} đã được tạo."
                fallback_outcome = "ticket_created"
            elif self._context.approval_decision == "rejected":
                fallback_answer = "Bạn đã từ chối bản nháp; hệ thống không tạo ticket."
                fallback_outcome = "approval_rejected"
            if fallback_answer is not None and fallback_outcome is not None:
                await self._context.progress(
                    "answer",
                    "completed",
                    "Đã ghi nhận kết quả thao tác.",
                )
                if self._on_text_delta is not None:
                    await self._on_text_delta(fallback_answer)
                return AgentRuntimeResult(
                    answer=fallback_answer,
                    outcome=fallback_outcome,
                    retrieval_calls=self._context.retrieval_calls,
                    tool_calls=self._context.tool_calls,
                )
            raise
        usage = streamed.context_wrapper.usage
        provider_request_id = next(
            (
                response.request_id or response.response_id or ""
                for response in reversed(streamed.raw_responses)
                if response.request_id or response.response_id
            ),
            "",
        )
        if self._usage_ledger is not None:
            await self._usage_ledger.complete(
                operation_id=self._operation_id,
                actual_input_tokens=usage.input_tokens,
                actual_output_tokens=usage.output_tokens,
                provider_request_id=provider_request_id,
            )
        if streamed.interruptions:
            if len(streamed.interruptions) != 1:
                raise RuntimeError("Only one approval interruption is allowed per run")
            interruption = streamed.interruptions[0]
            if interruption.name != "create_ticket" or interruption.arguments is None:
                raise RuntimeError("Agent requested an unsupported approval")
            proposal = CreateTicketArguments.model_validate_json(interruption.arguments)
            state = streamed.to_state().to_string(
                context_serializer=lambda _context: {},
                strict_context=True,
            )
            await self._context.progress(
                "approval",
                "waiting_approval",
                "Bản nháp ticket cần bạn xác nhận.",
            )
            return AgentRuntimeResult(
                answer=(
                    "Tôi đã chuẩn bị bản nháp ticket. Vui lòng kiểm tra nội dung và xác nhận "
                    "trước khi hệ thống tạo ticket."
                ),
                outcome="approval_required",
                approval_proposal=proposal.model_dump(mode="json"),
                serialized_state=state,
                approval_call_id=interruption.call_id,
                model_calls=usage.requests,
                retrieval_calls=self._context.retrieval_calls,
                tool_calls=self._context.tool_calls,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                provider_request_id=provider_request_id,
            )
        output = streamed.final_output_as(SupportAgentOutput)
        unknown = set(output.citations) - set(self._context.citation_store)
        if unknown:
            raise RuntimeError("Agent returned citations outside retrieved evidence")
        output = guard_support_output(
            output,
            policy=self._request_policy,
            retrieval_calls=self._context.retrieval_calls,
        )
        citations = [self._context.citation_store[source_id] for source_id in output.citations]
        answer = output.answer.strip()
        outcome = output.outcome
        if self._context.ticket_display_key is not None:
            outcome = "ticket_created"
        elif self._context.approval_decision == "rejected":
            outcome = "approval_rejected"
        await self._context.progress("answer", "completed", "Đã hoàn tất câu trả lời.")
        if self._on_text_delta is not None:
            await self._on_text_delta(answer)
        return AgentRuntimeResult(
            answer=answer,
            outcome=outcome,
            citations=citations,
            model_calls=usage.requests,
            retrieval_calls=self._context.retrieval_calls,
            tool_calls=self._context.tool_calls,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            provider_request_id=provider_request_id,
        )

    async def close(self) -> None:
        await self._client.close()


@dataclass(frozen=True, slots=True)
class OpenAIAgentsRuntimeFactory:
    api_key: str
    model: str
    usage_ledger: DatabaseUsageLedger | None = None

    def create(
        self,
        *,
        context: SupportSDKContext,
        operation_id: str,
        on_stream_started: StreamStartedCallback | None = None,
        on_text_delta: TextDeltaCallback | None = None,
    ) -> OpenAIAgentsRuntime:
        return OpenAIAgentsRuntime(
            api_key=self.api_key,
            model=self.model,
            context=context,
            operation_id=operation_id,
            usage_ledger=self.usage_ledger,
            on_stream_started=on_stream_started,
            on_text_delta=on_text_delta,
        )
