"""Concrete retrieval-augmented nodes for the support graph."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context.builder import ContextMessage, build_agent_context
from app.agent.graph import SupportGraphNodes
from app.agent.state import EvidenceState, SupportAgentState
from app.auth.principal import Principal
from app.observability import AIObserver, NoopAIObserver
from app.providers.base import StructuredResponseProvider
from app.providers.structured import EvidenceInput
from app.rag.citations.sources import InvalidCitationError, build_evidence_output
from app.rag.retrieval.query import RetrievalHit
from app.tools.results import ToolResult


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
        history: Sequence[ContextMessage] = (),
        minimum_lexical_coverage: float = 0.5,
        minimum_vector_similarity: float = 0.75,
        observer: AIObserver | None = None,
        model: str = "fake",
        tool_runner: ToolRunner | None = None,
    ) -> None:
        self._session = session
        self._principal = principal
        self._retriever = retriever
        self._provider = provider
        self._history = list(history)
        self._minimum_lexical_coverage = minimum_lexical_coverage
        self._minimum_vector_similarity = minimum_vector_similarity
        self._observer = observer or NoopAIObserver()
        self._model = model
        self._tool_runner = tool_runner
        self._hits: list[RetrievalHit] = []
        self._sources_by_id: dict[str, EvidenceInput] = {}

    async def load_context(self, state: SupportAgentState) -> dict[str, Any]:
        context = build_agent_context(current_query=state["query"], history=self._history)
        history = [
            {"role": message.role, "content": message.content} for message in context.history
        ]
        summary_parts = [
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
        return {
            "query": context.current_query,
            "history": history,
            "context_estimated_tokens": context.estimated_tokens,
            "context_truncated": context.truncated,
            "suggested_steps": list(context.suggested_steps),
            "confirmed_attempted_steps": list(context.confirmed_attempted_steps),
        }

    async def rewrite_query(self, state: SupportAgentState) -> dict[str, Any]:
        return {"normalized_query": " ".join(state["query"].strip().split())}

    async def decide_action(self, state: SupportAgentState) -> dict[str, Any]:
        if self._tool_runner is None:
            return {"action_route": "rag"}
        run_id = state.get("run_id", "preview")
        decision = await self._provider.choose_support_tool(
            state["query"],
            history=[(item["role"], item["content"]) for item in state.get("history", [])],
            operation_id=f"agent:{run_id}:tool-decision",
        )
        if decision.call is None:
            return {
                "action_route": "rag",
                "provider_request_id": decision.provider_request_id,
                "input_tokens": decision.input_tokens,
                "output_tokens": decision.output_tokens,
            }
        return {
            "action_route": "tool",
            "tool_call": decision.call.model_dump(mode="json"),
            "provider_request_id": decision.provider_request_id,
            "input_tokens": decision.input_tokens,
            "output_tokens": decision.output_tokens,
        }

    async def execute_tool(self, state: SupportAgentState) -> dict[str, Any]:
        call = state.get("tool_call")
        if self._tool_runner is None or not call:
            return {"tool_result": {"status": "failed", "error": {"code": "missing_tool"}}}
        raw_arguments = call.get("arguments")
        if not isinstance(raw_arguments, dict):
            return {
                "tool_result": {"status": "failed", "error": {"code": "invalid_arguments"}}
            }
        result = await self._tool_runner.execute(
            call_id=str(call["call_id"]),
            name=str(call["name"]),
            arguments=cast(dict[str, Any], raw_arguments),
        )
        return {
            "tool_result": result.model_dump(mode="json"),
            "tool_calls": state.get("tool_calls", 0) + 1,
        }

    async def respond_tool(self, state: SupportAgentState) -> dict[str, Any]:
        result = state.get("tool_result", {})
        error = result.get("error")
        call = state.get("tool_call", {})
        if (
            result.get("status") == "failed"
            and isinstance(error, dict)
            and error.get("code") == "approval_required"
            and call.get("name") == "create_ticket"
            and isinstance(call.get("arguments"), dict)
        ):
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
            return {
                "answer": "Không thể đọc dữ liệu hỗ trợ hiện tại. Vui lòng thử lại sau.",
                "citations": [],
                "citation_ids": [],
                "outcome": "no_answer",
                "route": "done",
            }
        data = cast(dict[str, Any], result["data"])
        if result.get("name") == "check_service_status":
            answer = (
                f"Trạng thái {data.get('service_id', 'dịch vụ')}: "
                f"{data.get('status', 'unknown')}. {data.get('message', '')}"
            ).strip()
        else:
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
        return {
            "answer": answer,
            "citations": [],
            "citation_ids": [],
            "outcome": "answered",
            "route": "done",
        }

    async def retrieve(self, state: SupportAgentState) -> dict[str, Any]:
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
        )
        scores = {str(hit.chunk_id): hit.score for hit in self._hits}
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
        return {"evidence": evidence}

    async def decide_evidence(self, state: SupportAgentState) -> dict[str, Any]:
        return {"route": "generate" if state.get("evidence") else "no_answer"}

    async def generate_answer(self, state: SupportAgentState) -> dict[str, Any]:
        run_id = state.get("run_id", "preview")
        with self._observer.generation(
            run_id=run_id,
            actor_id=state.get("actor_id", str(self._principal.user_id)),
            model=self._model,
            evidence_count=len(self._sources_by_id),
        ) as observation:
            response = await self._provider.generate_support_reply(
                state["query"],
                evidence=list(self._sources_by_id.values()),
                history=[(item["role"], item["content"]) for item in state.get("history", [])],
                operation_id=(f"rag:{run_id}:generation:{state.get('model_calls', 0) + 1}"),
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
            return {"route": "no_answer", "validation_errors": []}
        try:
            selected = build_evidence_output(
                self._hits,
                requested_source_ids=state.get("citation_ids", []),
                minimum_lexical_coverage=self._minimum_lexical_coverage,
                minimum_vector_similarity=self._minimum_vector_similarity,
            )
        except InvalidCitationError as exc:
            return {"route": "retry", "validation_errors": [str(exc)]}
        scores = {str(hit.chunk_id): hit.score for hit in self._hits}
        return {
            "route": "done",
            "outcome": "answered",
            "citations": [
                _evidence_state(source, scores[str(source.chunk_id)]) for source in selected.sources
            ],
            "validation_errors": [],
        }

    async def no_answer(self, state: SupportAgentState) -> dict[str, Any]:
        del state
        return {
            "answer": "Không tìm thấy tài liệu hiện hành đủ căn cứ để trả lời.",
            "citation_ids": [],
            "citations": [],
            "outcome": "no_answer",
            "route": "done",
        }

    def graph_nodes(self) -> SupportGraphNodes:
        return SupportGraphNodes(
            load_context=self.load_context,
            decide_action=self.decide_action,
            execute_tool=self.execute_tool,
            respond_tool=self.respond_tool,
            rewrite_query=self.rewrite_query,
            retrieve=self.retrieve,
            decide_evidence=self.decide_evidence,
            generate_answer=self.generate_answer,
            validate_answer=self.validate_answer,
            no_answer=self.no_answer,
        )
