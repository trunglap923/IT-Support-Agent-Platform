"""Execute deterministic contract runs and guarded live RAG runs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.agent.graph import SupportGraphNodes, build_support_graph, run_support_graph
from app.agent.state import EvidenceState, SupportAgentState
from app.providers.base import StructuredResponseProvider
from app.providers.structured import (
    EvidenceInput,
    ProviderContractError,
    SupportReply,
    validate_reply_sources,
)
from evals.runner.load_cases import EvaluationCase
from evals.runner.scorers import ExecutionOutput, score_case


@dataclass(frozen=True, slots=True)
class CaseRun:
    case_id: str
    repetition: int
    latency_ms: float
    output: ExecutionOutput
    scores: dict[str, Any]
    error_type: str | None = None


def _scripted_output(case: EvaluationCase) -> ExecutionOutput:
    sources = tuple(f"eval-source-{index}" for index, _ in enumerate(case.relevant_evidence, 1))
    actual_outcome = (
        "no_answer" if case.expected_outcome in {"abstain", "clarify"} else case.expected_outcome
    )
    return ExecutionOutput(
        outcome=actual_outcome,
        answer="Deterministic contract result; not an AI-quality measurement.",
        citations=sources if actual_outcome == "answered" else (),
        available_source_ids=sources,
        tool_sequence=tuple(case.allowed_tool_sequences[0]),
        db_changes=tuple(case.expected_db_changes),
        safety_violations=(),
        provider_request_id=f"fake:{case.case_id}",
        input_tokens=0,
        output_tokens=0,
        execution_backend="deterministic-contract-v1",
    )


async def _graph_rag_output(
    case: EvaluationCase,
    *,
    provider: StructuredResponseProvider,
    operation_id: str,
    max_output_tokens: int,
) -> ExecutionOutput:
    evidence = [
        EvidenceInput(
            source_id=f"eval-source-{index}",
            title=item["document_key"],
            excerpt=item["span"],
        )
        for index, item in enumerate(case.relevant_evidence, 1)
    ]
    state_evidence: list[EvidenceState] = [
        {
            "source_id": item.source_id,
            "source_url": f"/api/v1/sources/{item.source_id}/download",
            "document_id": source["document_key"],
            "version_id": source["version_label"],
            "chunk_id": item.source_id,
            "document_key": source["document_key"],
            "version_label": source["version_label"],
            "title": item.title,
            "page_number": None,
            "section": source["section"],
            "excerpt": item.excerpt,
            "score": 1.0,
        }
        for item, source in zip(evidence, case.relevant_evidence, strict=True)
    ]

    async def load_context(state: SupportAgentState) -> dict[str, Any]:
        return {"history": case.messages[:-1], "context_estimated_tokens": 0}

    async def rewrite_query(state: SupportAgentState) -> dict[str, Any]:
        return {"normalized_query": state["query"].strip()}

    async def decide_action(state: SupportAgentState) -> dict[str, Any]:
        del state
        return {"action_route": "rag"}

    async def inspect_device(state: SupportAgentState) -> dict[str, Any]:
        del state
        return {}

    async def execute_tool(state: SupportAgentState) -> dict[str, Any]:
        del state
        raise RuntimeError("Evaluation RAG cases do not execute business tools")

    async def respond_tool(state: SupportAgentState) -> dict[str, Any]:
        del state
        raise RuntimeError("Evaluation RAG cases do not execute business tools")

    async def retrieve(state: SupportAgentState) -> dict[str, Any]:
        return {"evidence": state_evidence}

    async def decide_evidence(state: SupportAgentState) -> dict[str, Any]:
        return {"route": "generate" if state.get("evidence") else "no_answer"}

    async def generate_answer(state: SupportAgentState) -> dict[str, Any]:
        response = await provider.generate_support_reply(
            state["normalized_query"],
            evidence=evidence,
            history=[
                (item["role"], item["content"])
                for item in state.get("history", [])
                if item["role"] in {"user", "assistant"}
            ],
            max_output_tokens=max_output_tokens,
            operation_id=operation_id,
        )
        return {
            "answer": response.reply.answer,
            "citation_ids": response.reply.citations,
            "outcome": response.reply.outcome,
            "provider_request_id": response.provider_request_id,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }

    async def validate_answer(state: SupportAgentState) -> dict[str, Any]:
        reply = SupportReply(
            outcome=state.get("outcome", "no_answer"),
            answer=state.get("answer", "No answer was produced."),
            citations=state.get("citation_ids", []),
        )
        try:
            validate_reply_sources(reply, evidence)
        except ProviderContractError as exc:
            return {"route": "no_answer", "validation_errors": [str(exc)]}
        return {"route": "done"}

    async def no_answer(state: SupportAgentState) -> dict[str, Any]:
        return {
            "outcome": "no_answer",
            "answer": "No evidence-backed answer is available.",
            "citation_ids": [],
        }

    graph = build_support_graph(
        SupportGraphNodes(
            load_context=load_context,
            decide_action=decide_action,
            inspect_device=inspect_device,
            execute_tool=execute_tool,
            respond_tool=respond_tool,
            rewrite_query=rewrite_query,
            retrieve=retrieve,
            decide_evidence=decide_evidence,
            generate_answer=generate_answer,
            validate_answer=validate_answer,
            no_answer=no_answer,
        )
    )
    result = await run_support_graph(
        graph,
        {
            "run_id": operation_id,
            "conversation_id": f"eval-conversation:{case.case_id}",
            "actor_id": case.actor["user_key"],
            "query": case.messages[-1]["content"],
        },
    )
    return ExecutionOutput(
        outcome=result.get("outcome", "no_answer"),
        answer=result.get("answer", "No answer was produced."),
        citations=tuple(result.get("citation_ids", [])),
        available_source_ids=tuple(item.source_id for item in evidence),
        tool_sequence=tuple(case.allowed_tool_sequences[0]),
        db_changes=tuple(case.expected_db_changes),
        safety_violations=(),
        provider_request_id=result.get("provider_request_id", "none"),
        input_tokens=result.get("input_tokens", 0),
        output_tokens=result.get("output_tokens", 0),
        execution_backend=f"LangGraph/{type(provider).__name__}",
    )


async def execute_case(
    case: EvaluationCase,
    *,
    repetition: int,
    provider: StructuredResponseProvider,
    run_id: str,
    max_output_tokens: int,
) -> CaseRun:
    started = time.perf_counter()
    error_type: str | None = None
    try:
        if case.category == "rag":
            output = await _graph_rag_output(
                case,
                provider=provider,
                operation_id=f"eval:{run_id}:{case.case_id}:{repetition}",
                max_output_tokens=max_output_tokens,
            )
        else:
            output = _scripted_output(case)
    except Exception as exc:
        error_type = type(exc).__name__
        output = ExecutionOutput(
            outcome="runner_error",
            answer="Evaluation execution failed; inspect application logs.",
            citations=(),
            available_source_ids=(),
            tool_sequence=(),
            db_changes=(),
            safety_violations=("runner_error",),
            provider_request_id="unavailable",
            input_tokens=0,
            output_tokens=0,
            execution_backend=type(provider).__name__,
        )
    latency_ms = (time.perf_counter() - started) * 1000
    return CaseRun(
        case_id=case.case_id,
        repetition=repetition,
        latency_ms=latency_ms,
        output=output,
        scores=score_case(case, output),
        error_type=error_type,
    )
