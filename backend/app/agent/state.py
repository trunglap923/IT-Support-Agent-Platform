"""Serializable state contract shared by the support-agent graph nodes."""

from __future__ import annotations

from typing import Literal, TypedDict

GRAPH_SCHEMA_VERSION = 1
MAX_MODEL_CALLS = 4
MAX_RETRIEVAL_CALLS = 4
GRAPH_RECURSION_LIMIT = 24

GraphRoute = Literal["generate", "no_answer", "done", "retry"]
ActionRoute = Literal["rag", "tool", "direct"]


class EvidenceState(TypedDict):
    source_id: str
    source_url: str
    document_id: str
    version_id: str
    chunk_id: str
    document_key: str
    version_label: str
    title: str
    page_number: int | None
    section: str | None
    excerpt: str
    score: float


class SupportAgentState(TypedDict, total=False):
    schema_version: int
    run_id: str
    conversation_id: str
    actor_id: str
    query: str
    normalized_query: str
    history: list[dict[str, str]]
    action_route: ActionRoute
    tool_call: dict[str, object]
    tool_result: dict[str, object]
    planned_steps: list[str]
    approval_proposal: dict[str, object]
    tool_calls: int
    context_estimated_tokens: int
    context_truncated: bool
    conversation_summary: str | None
    summarized_messages: int
    suggested_steps: list[str]
    confirmed_attempted_steps: list[str]
    evidence: list[EvidenceState]
    citations: list[EvidenceState]
    answer: str
    citation_ids: list[str]
    outcome: str
    route: GraphRoute
    model_calls: int
    retrieval_calls: int
    step_count: int
    validation_errors: list[str]
    stop_reason: str
    provider_request_id: str
    input_tokens: int
    output_tokens: int
