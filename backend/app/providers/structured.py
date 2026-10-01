"""Validated provider-neutral contract for support answers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

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


class SupportReply(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: Literal["answered", "no_answer"]
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


def validate_reply_sources(reply: SupportReply, evidence: list[EvidenceInput]) -> SupportReply:
    allowed = {item.source_id for item in evidence}
    unknown = set(reply.citations) - allowed
    if unknown:
        raise ProviderContractError(
            f"Provider returned citations outside retrieved evidence: {sorted(unknown)}"
        )
    return reply
