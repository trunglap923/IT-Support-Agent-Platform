"""Typed contract for deterministic Phase 0 context-baseline scenarios."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTEXT_BASELINE_CASE_VERSION: Literal["context-baseline-case-v1"] = (
    "context-baseline-case-v1"
)


class BaselineHistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["user", "assistant", "memory"]
    content: str = Field(min_length=1, max_length=32_000)


class BuilderOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_input_tokens: int = Field(default=10_000, ge=1)
    summary_trigger_messages: int = Field(default=20, ge=1)
    summary_trigger_tokens: int = Field(default=6_000, ge=1)
    recent_messages_after_summary: int = Field(default=12, ge=1)


class BaselineExpectations(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_error: str | None = Field(default=None, max_length=120)
    must_truncate: bool | None = None
    must_summarize: bool | None = None
    required_context_terms: tuple[str, ...] = Field(default=(), max_length=30)
    forbidden_context_terms: tuple[str, ...] = Field(default=(), max_length=30)
    required_confirmed_attempt_terms: tuple[str, ...] = Field(default=(), max_length=20)
    forbidden_confirmed_attempt_terms: tuple[str, ...] = Field(
        default=(), max_length=20
    )


class ContextBaselineCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["context-baseline-case-v1"] = CONTEXT_BASELINE_CASE_VERSION
    case_id: str = Field(pattern=r"^ctx-[0-9]{3}$")
    category: Literal[
        "latest_request",
        "follow_up",
        "exact_token",
        "attempt_state",
        "memory_selection",
        "token_budget",
        "compaction",
        "prompt_injection",
        "input_guard",
    ]
    description: str = Field(min_length=1, max_length=500)
    current_query: str = Field(min_length=1, max_length=40_000)
    history: tuple[BaselineHistoryMessage, ...] = Field(default=(), max_length=160)
    builder_options: BuilderOptions = BuilderOptions()
    expectations: BaselineExpectations

    @model_validator(mode="after")
    def has_an_observable_expectation(self) -> ContextBaselineCase:
        expected = self.expectations
        if not any(
            (
                expected.expected_error,
                expected.must_truncate is not None,
                expected.must_summarize is not None,
                expected.required_context_terms,
                expected.forbidden_context_terms,
                expected.required_confirmed_attempt_terms,
                expected.forbidden_confirmed_attempt_terms,
            )
        ):
            raise ValueError(
                "A baseline case must declare at least one observable expectation"
            )
        return self
