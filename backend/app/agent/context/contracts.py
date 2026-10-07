"""Versioned, provider-neutral contracts for active LLM context construction."""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ACTIVE_CONTEXT_SCHEMA_VERSION: Literal["active-context-v1"] = "active-context-v1"
CONTEXT_CANDIDATE_SCHEMA_VERSION: Literal["context-candidate-v1"] = "context-candidate-v1"
CONTEXT_BUILD_REQUEST_SCHEMA_VERSION: Literal["context-build-request-v1"] = (
    "context-build-request-v1"
)

ContextKind = Literal[
    "system_policy",
    "tool_schema",
    "current_request",
    "working_memory",
    "conversation_history",
    "semantic_memory",
    "episodic_memory",
    "procedural_memory",
    "knowledge",
    "tool_observation",
]
ContextPurpose = Literal["plan", "tool_selection", "answer", "verify", "memory_decision"]
ContextAction = Literal["keep", "drop", "summarize", "retrieve", "compress"]
Sensitivity = Literal["public", "internal", "confidential", "restricted"]


class ContextScope(BaseModel):
    """Server-derived isolation envelope attached before context selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: UUID | None = None
    owner_id: UUID | None = None
    department_id: UUID | None = None
    agent_namespace: str = Field(default="it_support", min_length=1, max_length=80)


class ContextCandidate(BaseModel):
    """A scoped item eligible for selection into one model invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["context-candidate-v1"] = CONTEXT_CANDIDATE_SCHEMA_VERSION
    candidate_id: str = Field(min_length=1, max_length=160)
    kind: ContextKind
    content: str = Field(min_length=1, max_length=32_000)
    source_ref: str = Field(min_length=1, max_length=500)
    scope: ContextScope
    relevance: float = Field(ge=0, le=1)
    importance: float = Field(ge=0, le=1)
    source_reliability: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    temporal_validity: float = Field(ge=0, le=1)
    task_utility: float = Field(ge=0, le=1)
    recency: float = Field(default=1.0, ge=0, le=1)
    token_cost: int = Field(ge=1)
    message_role: Literal["system", "user", "assistant", "tool"] | None = None
    sensitivity: Sensitivity = "internal"
    required: bool = False
    conflicts_with: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()


class ContextSelection(BaseModel):
    """Auditable selection decision; dropped content is not copied into the record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str = Field(min_length=1, max_length=160)
    action: ContextAction
    reason_code: str = Field(min_length=1, max_length=80)
    utility_score: float | None = Field(default=None, ge=-1, le=1)
    allocated_tokens: int = Field(default=0, ge=0)
    derived_artifact_ref: str | None = Field(default=None, max_length=500)


class ContextConflict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str = Field(min_length=1, max_length=240)
    predicate: str = Field(min_length=1, max_length=120)
    candidate_ids: tuple[str, ...] = Field(min_length=2)
    resolution: Literal[
        "authoritative_source",
        "newest_valid",
        "clarification_required",
        "quarantined",
    ]
    selected_candidate_id: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def selected_candidate_belongs_to_conflict(self) -> ContextConflict:
        if (
            self.selected_candidate_id is not None
            and self.selected_candidate_id not in self.candidate_ids
        ):
            raise ValueError("Selected conflict candidate must be part of the conflict")
        if self.resolution in {"clarification_required", "quarantined"}:
            if self.selected_candidate_id is not None:
                raise ValueError("Unresolved conflicts cannot select a candidate")
        elif self.selected_candidate_id is None:
            raise ValueError("Resolved conflicts require a selected candidate")
        return self


class ContextTokenBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model_context_limit: int = Field(ge=1)
    reserved_output_tokens: int = Field(ge=0)
    safety_margin_tokens: int = Field(ge=0)
    input_token_limit: int = Field(ge=1)

    @model_validator(mode="after")
    def input_budget_fits_model_limit(self) -> ContextTokenBudget:
        available = (
            self.model_context_limit - self.reserved_output_tokens - self.safety_margin_tokens
        )
        if available < 1 or self.input_token_limit > available:
            raise ValueError("Input token budget exceeds the available model context")
        return self


class ContextBuildRequest(BaseModel):
    """Provider-neutral input for selecting one bounded active context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["context-build-request-v1"] = CONTEXT_BUILD_REQUEST_SCHEMA_VERSION
    run_id: UUID
    call_sequence: int = Field(ge=1)
    purpose: ContextPurpose
    current_request: str = Field(min_length=1, max_length=32_000)
    current_request_candidate_id: str = Field(min_length=1, max_length=160)
    candidates: tuple[ContextCandidate, ...] = Field(min_length=1, max_length=500)
    token_budget: ContextTokenBudget
    policy_version: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_request_invariants(self) -> ContextBuildRequest:
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Context candidate IDs must be unique within a build request")
        current = [
            candidate
            for candidate in self.candidates
            if candidate.candidate_id == self.current_request_candidate_id
        ]
        if len(current) != 1:
            raise ValueError("Build request must identify exactly one current-request candidate")
        if current[0].kind != "current_request" or current[0].content != self.current_request:
            raise ValueError("Current-request candidate must preserve the current request verbatim")
        if not current[0].required:
            raise ValueError("Current-request candidate must be marked required")
        return self


class ActiveContextMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=64_000)
    candidate_ids: tuple[str, ...] = ()


class ActiveContext(BaseModel):
    """Immutable context bundle for exactly one model call."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["active-context-v1"] = ACTIVE_CONTEXT_SCHEMA_VERSION
    run_id: UUID
    call_sequence: int = Field(ge=1)
    purpose: ContextPurpose
    current_request: str = Field(min_length=1, max_length=32_000)
    messages: tuple[ActiveContextMessage, ...] = Field(min_length=1)
    selections: tuple[ContextSelection, ...]
    conflicts: tuple[ContextConflict, ...] = ()
    token_budget: ContextTokenBudget
    estimated_input_tokens: int = Field(ge=1)
    bundle_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_version: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_bundle_invariants(self) -> ActiveContext:
        if self.estimated_input_tokens > self.token_budget.input_token_limit:
            raise ValueError("Active context exceeds its declared input budget")
        current_request_messages = [
            message
            for message in self.messages
            if message.role == "user" and message.content == self.current_request
        ]
        if len(current_request_messages) != 1:
            raise ValueError("Active context must contain the current request exactly once")
        if self.messages[-1] != current_request_messages[0]:
            raise ValueError("Current request must be the final active-context message")
        candidate_ids = [selection.candidate_id for selection in self.selections]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("A context candidate may have only one final selection decision")
        return self


class ContextManager(Protocol):
    """Runtime-neutral interface implemented by the Phase 2 context manager."""

    def build(self, request: ContextBuildRequest) -> ActiveContext: ...
