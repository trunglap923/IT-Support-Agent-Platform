"""Resolve request intent and map it to the smallest safe agent tool set."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

from app.agent.context.builder import ContextMessage
from app.diagnostics import log_event
from app.rag.retrieval.analysis import (
    DeterministicQueryAnalyzer,
    ModelQueryAnalyzer,
    QueryAnalysisModel,
    QueryRewritePolicy,
)
from app.rag.retrieval.models import QuerySpec, RetrievalRequest

logger = logging.getLogger(__name__)

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

PreferredAction = Literal[
    "knowledge",
    "direct",
    "get_my_profile",
    "check_service_status",
    "get_my_open_tickets",
    "get_my_recent_tickets",
    "create_ticket",
]
RequestMode = Literal["new_request", "contextual_follow_up", "transform_previous"]


@dataclass(frozen=True, slots=True)
class AgentRequestPolicy:
    analysis: QuerySpec
    retrieval_query: str
    request_mode: RequestMode
    requires_knowledge: bool
    allowed_tools: frozenset[str]
    preferred_action: PreferredAction
    request_mode_confidence: float = 0
    analysis_model_calls: int = 0
    analysis_input_tokens: int = 0
    analysis_output_tokens: int = 0

    def allows(self, tool_name: str) -> bool:
        return tool_name in self.allowed_tools


def policy_for_analysis(
    analysis: QuerySpec,
    *,
    analysis_model_calls: int = 0,
    analysis_input_tokens: int = 0,
    analysis_output_tokens: int = 0,
    retrieval_query: str | None = None,
    request_mode: RequestMode = "new_request",
    request_mode_confidence: float = 0,
) -> AgentRequestPolicy:
    """Convert query intent to permissions without interpreting natural language here."""
    allowed: set[str] = set()
    preferred_action: PreferredAction = "direct"
    requires_knowledge = analysis.intent in {"knowledge", "incident"}

    if analysis.intent == "knowledge":
        allowed.update({"search_knowledge_base", "get_conversation_device"})
        preferred_action = "knowledge"
    elif analysis.intent == "incident":
        allowed.update(
            {
                "search_knowledge_base",
                "get_conversation_device",
                "check_service_status",
            }
        )
        preferred_action = "knowledge"
    elif analysis.intent == "service_status":
        allowed.add("check_service_status")
        preferred_action = "check_service_status"
    elif analysis.intent == "identity":
        allowed.add("get_my_profile")
        preferred_action = "get_my_profile"
    elif analysis.intent == "ticket_read":
        allowed.update({"get_my_open_tickets", "get_my_recent_tickets"})
        metadata = dict(analysis.metadata_filters)
        preferred_action = (
            "get_my_open_tickets"
            if metadata.get("ticket_scope") == "open"
            else "get_my_recent_tickets"
        )
    elif analysis.intent == "ticket_create":
        allowed.update({"create_ticket", "get_conversation_device"})
        preferred_action = "create_ticket"

    return AgentRequestPolicy(
        analysis=analysis,
        retrieval_query=retrieval_query or analysis.raw_query,
        request_mode=request_mode,
        requires_knowledge=requires_knowledge,
        allowed_tools=frozenset(allowed) & _ALL_TOOLS,
        preferred_action=preferred_action,
        request_mode_confidence=request_mode_confidence,
        analysis_model_calls=analysis_model_calls,
        analysis_input_tokens=analysis_input_tokens,
        analysis_output_tokens=analysis_output_tokens,
    )


def policy_for_request(query: str) -> AgentRequestPolicy:
    analysis = DeterministicQueryAnalyzer().analyze(RetrievalRequest(raw_query=query))
    return policy_for_analysis(analysis)


async def resolve_request_policy(
    query: str,
    *,
    model: QueryAnalysisModel,
    operation_id: str,
    rewrite_policy: QueryRewritePolicy | None = None,
    history: Sequence[ContextMessage] = (),
) -> AgentRequestPolicy:
    """Resolve intent and conversation relation before either runtime chooses an action."""

    request = RetrievalRequest(raw_query=query)
    analysis = DeterministicQueryAnalyzer().analyze(request)
    selected_policy = rewrite_policy or QueryRewritePolicy()
    model_analyzer = ModelQueryAnalyzer(
        model,
        max_calls=selected_policy.max_model_calls,
    )
    request_mode: RequestMode = "new_request"
    request_mode_confidence = 0.0
    retrieval_query = query.strip()
    history_items = tuple(
        (message.role, message.content)
        for message in history
        if message.role in {"user", "assistant"} and message.content.strip()
    )
    # A deterministic intent describes the current sentence, but cannot tell whether it
    # refers to an earlier answer. Ask the bounded analyzer to classify that relationship
    # whenever conversation context exists; otherwise use it only for low-confidence intent.
    needs_conversation_analysis = bool(history_items)
    if selected_policy.use_model(analysis) or needs_conversation_analysis:
        try:
            modeled_analysis = await model_analyzer.analyze(
                request,
                analysis,
                operation_id=operation_id,
                history=history_items,
            )
            response = model_analyzer.last_response
            if response is not None:
                request_mode_confidence = response.analysis.request_mode_confidence
                mode_is_confident = (
                    request_mode_confidence >= selected_policy.model_confidence_threshold
                )
                intent_is_confident = (
                    response.analysis.confidence >= selected_policy.model_confidence_threshold
                )
            else:
                mode_is_confident = False
                intent_is_confident = False
            if response is not None and (mode_is_confident or intent_is_confident):
                requested_mode = (
                    response.analysis.request_mode if mode_is_confident else "new_request"
                )
                if not history_items or (
                    requested_mode == "transform_previous"
                    and not any(role == "assistant" for role, _ in history_items)
                ):
                    requested_mode = "new_request"
                request_mode = requested_mode
                if request_mode == "transform_previous":
                    # A transformation reuses authorized conversation context and does not
                    # create a new knowledge claim that requires a fresh retrieval call.
                    analysis = replace(analysis, intent="social")
                elif request_mode == "contextual_follow_up":
                    contextual_query = response.analysis.retrieval_query
                    if contextual_query:
                        retrieval_query = contextual_query.strip()
                        if query.casefold() not in retrieval_query.casefold():
                            retrieval_query = f"{retrieval_query}\n{query.strip()}"
                        analysis = DeterministicQueryAnalyzer().analyze(
                            RetrievalRequest(raw_query=retrieval_query)
                        )
                        analysis = replace(
                            analysis,
                            intent=(
                                response.analysis.intent
                                if response.analysis.intent in {"knowledge", "incident"}
                                else "knowledge"
                            ),
                            confidence=max(
                                analysis.confidence,
                                response.analysis.confidence,
                            ),
                            analyzer="deterministic+conversation",
                        )
                elif selected_policy.use_model(analysis) and intent_is_confident:
                    analysis = modeled_analysis
        except Exception as error:
            log_event(
                logger,
                "agent.request_policy.model_fallback",
                operation_id=operation_id,
                error_type=type(error).__name__,
            )
    return policy_for_analysis(
        analysis,
        analysis_model_calls=model_analyzer.calls_used,
        analysis_input_tokens=model_analyzer.input_tokens,
        analysis_output_tokens=model_analyzer.output_tokens,
        retrieval_query=retrieval_query,
        request_mode=request_mode,
        request_mode_confidence=request_mode_confidence,
    )
