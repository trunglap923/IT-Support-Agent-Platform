"""Map structured current-query intent to the smallest safe agent tool set."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.rag.retrieval.analysis import DeterministicQueryAnalyzer
from app.rag.retrieval.models import QuerySpec, RetrievalRequest

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

    def allows(self, tool_name: str) -> bool:
        return tool_name in self.allowed_tools


def policy_for_analysis(analysis: QuerySpec) -> AgentRequestPolicy:
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
    )


def policy_for_request(query: str) -> AgentRequestPolicy:
    analysis = DeterministicQueryAnalyzer().analyze(RetrievalRequest(raw_query=query))
    return policy_for_analysis(analysis)
