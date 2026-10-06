"""Concrete retrieval-augmented nodes for the support graph."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context.builder import ContextMessage, build_agent_context
from app.agent.graph import SupportGraphNodes
from app.agent.request_policy import AgentRequestPolicy, policy_for_request
from app.agent.state import EvidenceState, SupportAgentState
from app.auth.principal import Principal
from app.db.models import Conversation, UserDevice
from app.diagnostics import content_log_fields, log_event
from app.observability import AIObserver, NoopAIObserver
from app.providers.base import StructuredResponseProvider, TextDeltaCallback
from app.providers.structured import (
    EvidenceInput,
    IncompleteStructuredResponseError,
    ProviderContractError,
    SupportExecutionPlan,
    SupportToolCall,
)
from app.rag.citations.sources import InvalidCitationError, build_evidence_output
from app.rag.retrieval.query import RetrievalHit
from app.tools.results import ToolResult

logger = logging.getLogger(__name__)


class Retriever(Protocol):
    async def search(
        self,
        session: AsyncSession,
        *,
        query: str,
        principal: Principal,
        operation_id: str,
    ) -> list[RetrievalHit]: ...


class ToolRunner(Protocol):
    async def execute(
        self, *, call_id: str, name: str, arguments: dict[str, Any]
    ) -> ToolResult: ...


ProgressCallback = Callable[[str, str, str | None, int | None], Awaitable[None]]


def _evidence_state(source: Any, score: float) -> EvidenceState:
    return {
        "source_id": source.source_id,
        "source_url": source.source_url,
        "document_id": str(source.document_id),
        "version_id": str(source.version_id),
        "chunk_id": str(source.chunk_id),
        "document_key": source.document_key,
        "version_label": source.version_label,
        "title": source.title,
        "page_number": source.page_number,
        "section": source.section,
        "excerpt": source.excerpt,
        "score": score,
    }


class RAGGraphNodes:
    def __init__(
        self,
        *,
        session: AsyncSession,
        principal: Principal,
        retriever: Retriever,
        provider: StructuredResponseProvider,
        request_policy: AgentRequestPolicy | None = None,
        history: Sequence[ContextMessage] = (),
        minimum_lexical_coverage: float = 0.5,
        minimum_vector_similarity: float = 0.75,
        minimum_evidence_score: float = 0.45,
        observer: AIObserver | None = None,
        model: str = "fake",
        tool_runner: ToolRunner | None = None,
        on_stream_started: Callable[[], Awaitable[None]] | None = None,
        on_text_delta: TextDeltaCallback | None = None,
        on_progress: ProgressCallback | None = None,
        log_prompts: bool = False,
    ) -> None:
        self._session = session
        self._principal = principal
        self._retriever = retriever
        self._provider = provider
        self._request_policy = request_policy
        self._history = list(history)
        self._minimum_lexical_coverage = minimum_lexical_coverage
        self._minimum_vector_similarity = minimum_vector_similarity
        self._minimum_evidence_score = minimum_evidence_score
        self._observer = observer or NoopAIObserver()
        self._model = model
        self._tool_runner = tool_runner
        self._on_stream_started = on_stream_started
        self._on_text_delta = on_text_delta
        self._on_progress = on_progress
        self._log_prompts = log_prompts
        self._hits: list[RetrievalHit] = []
        self._sources_by_id: dict[str, EvidenceInput] = {}

    async def _progress(
        self,
        stage: str,
        status: str,
        detail: str | None = None,
        count: int | None = None,
    ) -> None:
        if self._on_progress is not None:
            await self._on_progress(stage, status, detail, count)

    async def _plan(self, stages: Sequence[str]) -> None:
        for stage in stages:
            await self._progress(stage, "pending")

    async def _create_execution_plan(
        self,
        state: SupportAgentState,
        *,
        selected_action: str,
    ) -> tuple[SupportExecutionPlan, list[str], int, int, str]:
        run_id = state.get("run_id", "preview")
        plan_response = await self._provider.plan_support_steps(
            state["query"],
            selected_action=selected_action,
            history=[(item["role"], item["content"]) for item in state.get("history", [])],
            operation_id=f"agent:{run_id}:execution-plan",
        )
        if selected_action != "auto" and plan_response.plan.action != selected_action:
            raise ProviderContractError("Execution plan changed the selected action")
        planned_steps = [str(step) for step in plan_response.plan.steps]
        await self._progress("analyze", "completed", "Đã lập kế hoạch xử lý phù hợp.")
        await self._plan(planned_steps)
        return (
            plan_response.plan,
            planned_steps,
            plan_response.input_tokens,
            plan_response.output_tokens,
            plan_response.provider_request_id,
        )

    def _log(self, event: str, state: SupportAgentState, **fields: Any) -> None:
        log_event(
            logger,
            event,
            run_id=state.get("run_id", "preview"),
            step_count=state.get("step_count", 0),
            **fields,
        )

    async def load_context(self, state: SupportAgentState) -> dict[str, Any]:
        context = build_agent_context(current_query=state["query"], history=self._history)
        history = [
            {"role": message.role, "content": message.content} for message in context.history
        ]
        summary_parts = [
            *([context.conversation_summary] if context.conversation_summary else []),
            *(f"Suggested step: {step}" for step in context.suggested_steps),
            *(
                f"User-confirmed attempted step: {step}"
                for step in context.confirmed_attempted_steps
            ),
        ]
        if summary_parts:
            history.append(
                {
                    "role": "context_summary",
                    "content": "\n".join(summary_parts),
                }
            )
        update = {
            "query": context.current_query,
            "history": history,
            "context_estimated_tokens": context.estimated_tokens,
            "context_truncated": context.truncated,
            "conversation_summary": context.conversation_summary,
            "summarized_messages": context.summarized_messages,
            "suggested_steps": list(context.suggested_steps),
            "confirmed_attempted_steps": list(context.confirmed_attempted_steps),
        }
        self._log(
            "agent.context.loaded",
            state,
            history_messages=len(history),
            estimated_tokens=context.estimated_tokens,
            truncated=context.truncated,
            summarized_messages=context.summarized_messages,
            suggested_steps=len(context.suggested_steps),
            confirmed_attempted_steps=len(context.confirmed_attempted_steps),
        )
        return update

    async def rewrite_query(self, state: SupportAgentState) -> dict[str, Any]:
        normalized_query = " ".join(state["query"].strip().split())
        self._log(
            "agent.query.rewritten",
            state,
            changed=normalized_query != state["query"],
            **content_log_fields(
                "normalized_query",
                normalized_query,
                include_content=self._log_prompts,
            ),
        )
        return {"normalized_query": normalized_query}

    async def decide_action(self, state: SupportAgentState) -> dict[str, Any]:
        run_id = state.get("run_id", "preview")
        started_at = time.monotonic()
        self._log("agent.plan.started", state)
        request_policy = self._request_policy or policy_for_request(state["query"])
        selected_action = request_policy.preferred_action
        (
            plan,
            planned_steps,
            plan_input,
            plan_output,
            provider_request_id,
        ) = await self._create_execution_plan(
            state,
            selected_action=selected_action,
        )
        planned_action = plan.action
        if planned_action == "direct":
            action_route = "direct"
        elif planned_action == "knowledge":
            action_route = "rag"
        else:
            action_route = "tool"
        tool_call: SupportToolCall | None = None
        if action_route == "tool":
            if self._tool_runner is None:
                raise ProviderContractError("Execution plan requires tools but tools are disabled")
            tool_call = SupportToolCall.model_validate(
                {
                    "call_id": f"plan:{run_id}",
                    "name": planned_action,
                    "arguments": plan.tool_arguments(),
                }
            )
        self._log(
            "agent.action.decided",
            state,
            route=action_route,
            tool_name=tool_call.name if tool_call is not None else None,
            tool_call_id=tool_call.call_id if tool_call is not None else None,
            provider_request_id=provider_request_id,
            query_intent=request_policy.analysis.intent,
            query_confidence=round(request_policy.analysis.confidence, 4),
            input_tokens=plan_input,
            output_tokens=plan_output,
            duration_ms=round((time.monotonic() - started_at) * 1_000, 2),
        )
        update: dict[str, Any] = {
            "action_route": action_route,
            "planned_steps": planned_steps,
            "_model_calls_used": 1,
            "provider_request_id": provider_request_id,
            "input_tokens": plan_input,
            "output_tokens": plan_output,
        }
        if tool_call is not None:
            update["tool_call"] = tool_call.model_dump(mode="json")
        return update

    async def inspect_device(self, state: SupportAgentState) -> dict[str, Any]:
        await self._progress("device", "started", "Đang đọc thiết bị gắn với hội thoại.")
        try:
            conversation_id = UUID(state["conversation_id"])
        except (KeyError, ValueError):
            await self._progress("device", "warning", "Hội thoại chưa gắn thiết bị.")
            return {}
        device = await self._session.scalar(
            select(UserDevice)
            .join(Conversation, Conversation.device_id == UserDevice.id)
            .where(
                Conversation.id == conversation_id,
                Conversation.owner_id == self._principal.user_id,
                UserDevice.owner_id == self._principal.user_id,
                UserDevice.active.is_(True),
            )
        )
        if device is None:
            await self._progress("device", "warning", "Hội thoại chưa gắn thiết bị.")
            return {}
        platform_labels = {
            "windows": "Windows",
            "macos": "macOS",
            "linux": "Linux",
            "other": "Thiết bị khác",
        }
        platform = platform_labels.get(device.platform, "Thiết bị khác")
        await self._progress("device", "completed", f"{device.label} · {platform}")
        return {}

    async def execute_tool(self, state: SupportAgentState) -> dict[str, Any]:
        call = state.get("tool_call")
        if self._tool_runner is None or not call:
            return {"tool_result": {"status": "failed", "error": {"code": "missing_tool"}}}
        raw_arguments = call.get("arguments")
        if not isinstance(raw_arguments, dict):
            return {"tool_result": {"status": "failed", "error": {"code": "invalid_arguments"}}}
        tool_name = str(call["name"])
        stage_by_tool = {
            "get_my_profile": "profile",
            "check_service_status": "service",
            "get_my_open_tickets": "support_data",
            "get_my_recent_tickets": "support_data",
            "create_ticket": "approval",
        }
        stage = stage_by_tool.get(tool_name, "support_data")
        service_labels = {
            "vpn": "VPN Gateway",
            "registry": "Docker Registry",
            "gitlab": "GitLab",
        }
        service_id = raw_arguments.get("service_id")
        service_label = (
            service_labels.get(service_id, "dịch vụ") if isinstance(service_id, str) else "dịch vụ"
        )
        await self._progress(
            stage,
            "started",
            (
                f"Đang kiểm tra {service_label}."
                if stage == "service"
                else "Đang đọc thông tin tài khoản."
                if stage == "profile"
                else "Đang chuẩn bị bản nháp cần xác nhận."
                if stage == "approval"
                else "Đang kiểm tra thông tin hỗ trợ."
            ),
        )
        result = await self._tool_runner.execute(
            call_id=str(call["call_id"]),
            name=str(call["name"]),
            arguments=cast(dict[str, Any], raw_arguments),
        )
        self._log(
            "agent.tool.executed",
            state,
            tool_name=str(call["name"]),
            tool_call_id=str(call["call_id"]),
            status=result.status,
            error_code=result.error.code if result.error is not None else None,
        )
        if result.status == "success" and stage == "service":
            data = result.data if isinstance(result.data, dict) else {}
            status = data.get("status")
            safe_status = (
                status if status in {"healthy", "degraded", "down", "unknown"} else "unknown"
            )
            await self._progress("service", "completed", f"{service_label}: {safe_status}.")
        elif result.status == "success" and stage == "profile":
            await self._progress("profile", "completed", "Đã xác thực tài khoản hiện tại.")
        elif result.status == "success":
            await self._progress("support_data", "completed", "Đã tải thông tin ticket.")
        elif (
            stage == "approval"
            and result.error is not None
            and result.error.code == "approval_required"
        ):
            pass
        else:
            await self._progress(
                stage,
                "warning",
                "Chưa thể tải dữ liệu; sẽ nêu trong câu trả lời.",
            )
        return {
            "tool_result": result.model_dump(mode="json"),
            "tool_calls": state.get("tool_calls", 0) + 1,
        }

    async def respond_tool(self, state: SupportAgentState) -> dict[str, Any]:
        result = state.get("tool_result", {})
        error = result.get("error")
        call = state.get("tool_call", {})
        self._log(
            "agent.tool.response.prepared",
            state,
            tool_name=call.get("name"),
            status=result.get("status"),
            error_code=error.get("code") if isinstance(error, dict) else None,
        )
        if (
            result.get("status") == "failed"
            and isinstance(error, dict)
            and error.get("code") == "approval_required"
            and call.get("name") == "create_ticket"
            and isinstance(call.get("arguments"), dict)
        ):
            await self._progress(
                "approval",
                "waiting_approval",
                "Bản nháp ticket cần bạn xác nhận.",
            )
            arguments = cast(dict[str, Any], call["arguments"])
            return {
                "answer": (
                    "Tôi đã chuẩn bị bản nháp ticket. Vui lòng kiểm tra nội dung và xác nhận "
                    "trước khi hệ thống tạo ticket."
                ),
                "citations": [],
                "citation_ids": [],
                "outcome": "approval_required",
                "approval_proposal": arguments,
                "route": "done",
            }
        if result.get("status") != "success" or not isinstance(result.get("data"), dict):
            await self._progress("answer", "warning", "Đang chuẩn bị hướng xử lý thay thế.")
            return {
                "answer": "Không thể đọc dữ liệu hỗ trợ hiện tại. Vui lòng thử lại sau.",
                "citations": [],
                "citation_ids": [],
                "outcome": "no_answer",
                "route": "done",
            }
        data = cast(dict[str, Any], result["data"])
        await self._progress("answer", "started")
        if result.get("name") == "get_my_profile":
            display_name = str(data.get("display_name", "")).strip()
            answer = (
                f"Tên hiển thị trong tài khoản của bạn là **{display_name}**."
                if display_name
                else "Tài khoản hiện tại chưa có tên hiển thị."
            )
        elif result.get("name") == "check_service_status":
            answer = (
                f"Trạng thái {data.get('service_id', 'dịch vụ')}: "
                f"{data.get('status', 'unknown')}. {data.get('message', '')}"
            ).strip()
        elif result.get("name") == "get_my_open_tickets":
            tickets = data.get("tickets", [])
            if tickets:
                lines = [
                    f"- {item.get('display_key', 'Ticket')}: {item.get('title', '')} "
                    f"({item.get('status', 'unknown')})"
                    for item in tickets
                    if isinstance(item, dict)
                ]
                answer = "Các ticket đang mở của bạn:\n" + "\n".join(lines)
            else:
                answer = "Bạn không có ticket đang mở."
        else:
            tickets = data.get("tickets", [])
            if tickets:
                lines = [
                    f"- {item.get('display_key', 'Ticket')}: {item.get('title', '')} "
                    f"({item.get('status', 'unknown')})"
                    for item in tickets
                    if isinstance(item, dict)
                ]
                answer = "Các ticket gần đây của bạn:\n" + "\n".join(lines)
            else:
                answer = "Bạn chưa có ticket nào gần đây."
        await self._progress("answer", "completed", "Đã tổng hợp thông tin hỗ trợ.")
        return {
            "answer": answer,
            "citations": [],
            "citation_ids": [],
            "outcome": "answered",
            "route": "done",
        }

    async def retrieve(self, state: SupportAgentState) -> dict[str, Any]:
        await self._progress("knowledge", "started")
        operation_id = f"rag:{state.get('run_id', 'preview')}:retrieve"
        self._hits = await self._retriever.search(
            self._session,
            query=state.get("normalized_query", state["query"]),
            principal=self._principal,
            operation_id=operation_id,
        )
        output = build_evidence_output(
            self._hits,
            minimum_lexical_coverage=self._minimum_lexical_coverage,
            minimum_vector_similarity=self._minimum_vector_similarity,
            minimum_evidence_score=self._minimum_evidence_score,
        )
        scores = {
            str(hit.chunk_id): (hit.evidence_score if hit.evidence_score is not None else hit.score)
            for hit in self._hits
        }
        evidence = [
            _evidence_state(source, scores[str(source.chunk_id)]) for source in output.sources
        ]
        self._sources_by_id = {
            item["source_id"]: EvidenceInput(
                source_id=item["source_id"],
                title=item["title"],
                page_number=item["page_number"],
                excerpt=item["excerpt"],
            )
            for item in evidence
        }
        self._log(
            "agent.evidence.selected",
            state,
            retrieval_hits=len(self._hits),
            accepted_evidence=len(evidence),
            minimum_lexical_coverage=self._minimum_lexical_coverage,
            minimum_vector_similarity=self._minimum_vector_similarity,
            minimum_evidence_score=self._minimum_evidence_score,
            sources=[
                {
                    "source_id": item["source_id"],
                    "document_key": item["document_key"],
                    "title": item["title"],
                    "page_number": item["page_number"],
                    "score": round(float(item["score"]), 6),
                    **content_log_fields(
                        "excerpt",
                        str(item["excerpt"]),
                        include_content=self._log_prompts,
                    ),
                }
                for item in evidence
            ],
        )
        document_count = len({str(item["document_id"]) for item in evidence})
        await self._progress(
            "knowledge",
            "completed",
            f"Tìm thấy {document_count} tài liệu liên quan.",
            document_count,
        )
        return {"evidence": evidence}

    async def decide_evidence(self, state: SupportAgentState) -> dict[str, Any]:
        route = "no_answer" if state.get("stop_reason") else "generate"
        self._log(
            "agent.evidence.decided",
            state,
            route=route,
            evidence_count=len(state.get("evidence", [])),
            grounding_mode="internal" if state.get("evidence") else "general",
        )
        return {"route": route}

    async def generate_answer(self, state: SupportAgentState) -> dict[str, Any]:
        await self._progress("answer", "started")
        run_id = state.get("run_id", "preview")
        generation = state.get("model_calls", 0) + 1
        operation_id = f"rag:{run_id}:generation:{generation}"
        output_token_limits = (800, 1_200)
        retry_instruction: str | None = None
        retry_suffix = "incomplete-retry"
        with self._observer.generation(
            run_id=run_id,
            actor_id=state.get("actor_id", str(self._principal.user_id)),
            model=self._model,
            evidence_count=len(self._sources_by_id),
        ) as observation:
            for attempt, output_token_limit in enumerate(output_token_limits):
                attempt_started_at = time.monotonic()
                self._log(
                    "agent.generation.started",
                    state,
                    attempt=attempt + 1,
                    operation_id=(
                        operation_id if attempt == 0 else f"{operation_id}:{retry_suffix}"
                    ),
                    model=self._model,
                    evidence_count=len(self._sources_by_id),
                    max_output_tokens=output_token_limit,
                )
                if self._on_stream_started is not None:
                    await self._on_stream_started()
                try:
                    response = await self._provider.generate_support_reply(
                        state["query"],
                        evidence=list(self._sources_by_id.values()),
                        history=[
                            (item["role"], item["content"]) for item in state.get("history", [])
                        ],
                        max_output_tokens=output_token_limit,
                        operation_id=(
                            operation_id if attempt == 0 else f"{operation_id}:{retry_suffix}"
                        ),
                        on_text_delta=self._on_text_delta,
                        retry_instruction=retry_instruction,
                    )
                    break
                except IncompleteStructuredResponseError as error:
                    self._log(
                        "agent.generation.incomplete",
                        state,
                        attempt=attempt + 1,
                        duration_ms=round((time.monotonic() - attempt_started_at) * 1_000, 2),
                        retrying=attempt < len(output_token_limits) - 1,
                        error=str(error),
                    )
                    if attempt == len(output_token_limits) - 1:
                        raise
                    retry_suffix = "incomplete-retry"
                    retry_instruction = (
                        "The previous response was truncated. Return one complete response "
                        "within the output limit and obey the support-reply contract."
                    )
                except ProviderContractError as error:
                    self._log(
                        "agent.generation.invalid",
                        state,
                        attempt=attempt + 1,
                        duration_ms=round((time.monotonic() - attempt_started_at) * 1_000, 2),
                        retrying=attempt < len(output_token_limits) - 1,
                        error=str(error),
                    )
                    if attempt == len(output_token_limits) - 1:
                        if self._on_stream_started is not None:
                            await self._on_stream_started()
                        fallback_answer = (
                            "Không tìm thấy tài liệu hiện hành đủ căn cứ để trả lời. "
                            "Vui lòng liên hệ IT để được hỗ trợ."
                        )
                        self._log(
                            "agent.generation.fallback",
                            state,
                            reason="structured_contract_violation",
                            outcome="no_answer",
                        )
                        if observation is not None:
                            observation.update(
                                output={"outcome": "no_answer", "citation_count": 0},
                                usage_details={"input_tokens": 0, "output_tokens": 0},
                            )
                        return {
                            "answer": fallback_answer,
                            "citation_ids": [],
                            "outcome": "no_answer",
                            "provider_request_id": "",
                            "input_tokens": 0,
                            "output_tokens": 0,
                        }
                    retry_suffix = "contract-retry"
                    retry_instruction = (
                        "The previous response violated the support-reply contract. Use "
                        "outcome='answered' only with one or more allowed source IDs. Use "
                        "outcome='no_answer' only with citations=[]. Do not cite adjacent "
                        "evidence that is insufficient to answer the query."
                    )
            if observation is not None:
                observation.update(
                    output={
                        "outcome": response.reply.outcome,
                        "citation_count": len(response.reply.citations),
                    },
                    usage_details={
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                    },
                )
        self._log(
            "agent.generation.completed",
            state,
            provider_request_id=response.provider_request_id,
            outcome=response.reply.outcome,
            citation_ids=response.reply.citations,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            duration_ms=round((time.monotonic() - attempt_started_at) * 1_000, 2),
            **content_log_fields(
                "answer",
                response.reply.answer,
                include_content=self._log_prompts,
            ),
        )
        return {
            "answer": response.reply.answer,
            "citation_ids": response.reply.citations,
            "outcome": response.reply.outcome,
            "provider_request_id": response.provider_request_id,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }

    async def validate_answer(self, state: SupportAgentState) -> dict[str, Any]:
        if state.get("outcome") == "no_answer":
            await self._progress("answer", "warning", "Thiếu nguồn đủ căn cứ để trả lời.")
            self._log("agent.answer.validated", state, route="no_answer", errors=[])
            return {"route": "no_answer", "validation_errors": []}
        if state.get("outcome") == "needs_information":
            await self._progress("answer", "completed", "Cần thêm thông tin từ người dùng.")
            self._log("agent.answer.validated", state, route="done", errors=[])
            return {
                "route": "done",
                "outcome": "needs_information",
                "citations": [],
                "validation_errors": [],
            }
        try:
            selected = build_evidence_output(
                self._hits,
                requested_source_ids=state.get("citation_ids", []),
                minimum_lexical_coverage=self._minimum_lexical_coverage,
                minimum_vector_similarity=self._minimum_vector_similarity,
                minimum_evidence_score=self._minimum_evidence_score,
            )
        except InvalidCitationError as exc:
            await self._progress("answer", "warning", "Đang kiểm tra lại nguồn tham chiếu.")
            self._log("agent.answer.validated", state, route="retry", errors=[str(exc)])
            return {"route": "retry", "validation_errors": [str(exc)]}
        scores = {str(hit.chunk_id): hit.score for hit in self._hits}
        self._log(
            "agent.answer.validated",
            state,
            route="done",
            errors=[],
            selected_sources=len(selected.sources),
        )
        await self._progress("answer", "completed", "Đã kiểm tra nguồn tham chiếu.")
        return {
            "route": "done",
            "outcome": "answered",
            "citations": [
                _evidence_state(source, scores[str(source.chunk_id)]) for source in selected.sources
            ],
            "validation_errors": [],
        }

    async def no_answer(self, state: SupportAgentState) -> dict[str, Any]:
        generated_answer = state.get("answer")
        if (
            state.get("outcome") == "no_answer"
            and isinstance(generated_answer, str)
            and generated_answer.strip()
        ):
            answer = generated_answer.strip()
            preserve_generated_answer = True
        else:
            answer = "Không tìm thấy tài liệu hiện hành đủ căn cứ để trả lời."
            preserve_generated_answer = False
        self._log(
            "agent.no_answer",
            state,
            stop_reason=state.get("stop_reason"),
            validation_errors=state.get("validation_errors", []),
            preserved_generated_answer=preserve_generated_answer,
        )
        await self._progress("answer", "completed", "Đã hoàn tất hướng dẫn.")
        return {
            "answer": answer,
            "citation_ids": [],
            "citations": [],
            "outcome": "no_answer",
            "route": "done",
        }

    def graph_nodes(self) -> SupportGraphNodes:
        return SupportGraphNodes(
            load_context=self.load_context,
            decide_action=self.decide_action,
            inspect_device=self.inspect_device,
            execute_tool=self.execute_tool,
            respond_tool=self.respond_tool,
            rewrite_query=self.rewrite_query,
            retrieve=self.retrieve,
            decide_evidence=self.decide_evidence,
            generate_answer=self.generate_answer,
            validate_answer=self.validate_answer,
            no_answer=self.no_answer,
        )
