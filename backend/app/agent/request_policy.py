"""Map structured current-query intent to the smallest safe agent tool set."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

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


@dataclass(frozen=True, slots=True)
class AgentRequestPolicy:
    analysis: QuerySpec
    requires_knowledge: bool
    allowed_tools: frozenset[str]
    preferred_action: PreferredAction
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
        requires_knowledge=requires_knowledge,
        allowed_tools=frozenset(allowed) & _ALL_TOOLS,
        preferred_action=preferred_action,
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
) -> AgentRequestPolicy:
    """Resolve low-confidence intent once before either agent runtime chooses an action."""

    request = RetrievalRequest(raw_query=query)
    analysis = DeterministicQueryAnalyzer().analyze(request)
    selected_policy = rewrite_policy or QueryRewritePolicy()
    model_analyzer = ModelQueryAnalyzer(
        model,
        max_calls=selected_policy.max_model_calls,
    )
    if selected_policy.use_model(analysis):
        try:
            modeled_analysis = await model_analyzer.analyze(
                request,
                analysis,
                operation_id=operation_id,
            )
            if selected_policy.accept_model(modeled_analysis):
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
    )
