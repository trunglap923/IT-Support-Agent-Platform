"""Validated provider-neutral contract for support answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProviderContractError(ValueError):
    """Raised when a provider returns data outside the application contract."""


class IncompleteStructuredResponseError(ProviderContractError):
    """Raised when a provider stops before completing structured output."""


class InvalidStructuredResponseError(ProviderContractError):
    """Raised when a complete response violates the structured reply contract."""


class SupportToolCall(BaseModel):
    """A side-effect-free tool proposal; trusted actor context is never model supplied."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str = Field(min_length=1, max_length=160)
    name: Literal[
        "get_my_profile",
        "check_service_status",
        "get_my_open_tickets",
        "get_my_recent_tickets",
        "create_ticket",
    ]
    arguments: dict[str, Any]


PlanStage = Literal[
    "device",
    "profile",
    "service",
    "support_data",
    "knowledge",
    "approval",
    "answer",
]


class SupportExecutionPlan(BaseModel):
    """Short observable action plan; never model reasoning or chain-of-thought."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Literal[
        "knowledge",
        "direct",
        "get_my_profile",
        "check_service_status",
        "get_my_open_tickets",
        "get_my_recent_tickets",
        "create_ticket",
    ]
    steps: list[PlanStage] = Field(min_length=1, max_length=4)
    service_id: Literal["vpn", "registry", "gitlab"] | None = None
    ticket_title: str | None = Field(default=None, min_length=5, max_length=160)
    ticket_description: str | None = Field(default=None, min_length=10, max_length=4_000)
    ticket_issue_type: Literal["vpn", "docker", "gitlab", "other"] | None = None
    ticket_severity: Literal["low", "normal", "high"] | None = None
    ticket_device_id: UUID | None = None

    @field_validator("steps")
    @classmethod
    def unique_steps(cls, values: list[PlanStage]) -> list[PlanStage]:
        if len(values) != len(set(values)):
            raise ValueError("Execution plan steps must be unique")
        return values

    @model_validator(mode="after")
    def matches_selected_action(self) -> SupportExecutionPlan:
        action_stage: dict[str, PlanStage | None] = {
            "knowledge": "knowledge",
            "direct": None,
            "get_my_profile": "profile",
            "check_service_status": "service",
            "get_my_open_tickets": "support_data",
            "get_my_recent_tickets": "support_data",
            "create_ticket": "approval",
        }
        required = action_stage[self.action]
        if required is not None and required not in self.steps:
            raise ValueError("Execution plan must include the selected action")
        if self.action == "create_ticket":
            if self.steps[-1] != "approval":
                raise ValueError("Ticket creation plans must end with approval")
            if not all((self.ticket_title, self.ticket_description, self.ticket_issue_type)):
                raise ValueError("Ticket creation plans require complete draft fields")
        elif self.steps[-1] != "answer":
            raise ValueError("Read and knowledge plans must end with an answer")
        if self.action == "check_service_status" and self.service_id is None:
            raise ValueError("Service status plans require a service_id")
        return self

    def tool_arguments(self) -> dict[str, Any]:
        if self.action == "check_service_status":
            return {"service_id": self.service_id}
        if self.action == "create_ticket":
            return {
                "title": self.ticket_title,
                "description": self.ticket_description,
                "issue_type": self.ticket_issue_type,
                "severity": self.ticket_severity or "normal",
                "device_id": str(self.ticket_device_id) if self.ticket_device_id else None,
            }
        return {}


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=300)
    page_number: int | None = Field(default=None, ge=1)
    excerpt: str = Field(min_length=1, max_length=2_000)

    @field_validator("source_id", "title", "excerpt")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class QueryAnalysisOutput(BaseModel):
    """Bounded model contribution to query analysis; deterministic fields are merged later."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    intent: Literal[
        "knowledge",
        "incident",
        "service_status",
        "identity",
        "ticket_read",
        "ticket_create",
        "social",
        "memory",
        "unknown",
    ]
    semantic_query: str = Field(min_length=1, max_length=1_000)
    exact_terms: list[str] = Field(default_factory=list, max_length=20)
    services: list[str] = Field(default_factory=list, max_length=5)
    products: list[str] = Field(default_factory=list, max_length=5)
    operating_systems: list[str] = Field(default_factory=list, max_length=5)
    error_codes: list[str] = Field(default_factory=list, max_length=20)
    versions: list[str] = Field(default_factory=list, max_length=10)
    version_scope: Literal["current", "specific", "historical"] = "current"
    confidence: float = Field(ge=0, le=1)

    @field_validator(
        "semantic_query",
        "exact_terms",
        "services",
        "products",
        "operating_systems",
        "error_codes",
        "versions",
    )
    @classmethod
    def normalize_query_fields(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
        return value


class SupportReply(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: Literal["answered", "no_answer", "needs_information"]
    answer: str = Field(min_length=1, max_length=4_000)
    citations: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("answer")
    @classmethod
    def strip_answer(cls, value: str) -> str:
        return value.strip()

    @field_validator("citations")
    @classmethod
    def normalize_citations(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            source_id = value.strip()
            if source_id and source_id not in normalized:
                normalized.append(source_id)
        return normalized

    @model_validator(mode="after")
    def enforce_outcome(self) -> SupportReply:
        if self.outcome == "answered" and not self.citations:
            raise ValueError("An answered reply requires at least one citation")
        if self.outcome == "no_answer" and self.citations:
            raise ValueError("A no-answer reply cannot contain citations")
        if self.outcome == "needs_information" and self.citations:
            raise ValueError("A needs-information reply cannot contain citations")
        if self.outcome == "needs_information" and "?" not in self.answer:
            raise ValueError("A needs-information reply must ask a question")
        return self


@dataclass(frozen=True, slots=True)
class StructuredModelResponse:
    reply: SupportReply
    provider_request_id: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class ToolDecisionResponse:
    call: SupportToolCall | None
    provider_request_id: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class ExecutionPlanResponse:
    plan: SupportExecutionPlan
    provider_request_id: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class QueryAnalysisResponse:
    analysis: QueryAnalysisOutput
    provider_request_id: str
    input_tokens: int
    output_tokens: int


def validate_reply_sources(reply: SupportReply, evidence: list[EvidenceInput]) -> SupportReply:
    allowed = {item.source_id for item in evidence}
    unknown = set(reply.citations) - allowed
    if unknown:
        raise ProviderContractError(
            f"Provider returned citations outside retrieved evidence: {sorted(unknown)}"
        )
    return reply
