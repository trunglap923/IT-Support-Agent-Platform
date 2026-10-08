"""Strict contracts for procedure candidates and review actions."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SignalType = Literal["service", "product", "operating_system", "error_code", "version"]


class ApplicabilitySignal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    signal_type: SignalType
    value: str = Field(min_length=1, max_length=160)

    @field_validator("value")
    @classmethod
    def normalize_value(cls, value: str) -> str:
        return " ".join(value.casefold().split())


class ProcedureStepDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    step_key: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    action: str = Field(min_length=3, max_length=500)
    tool_name: str | None = Field(default=None, max_length=80)
    expected_observation: str = Field(min_length=3, max_length=500)
    on_success: str | None = Field(default=None, max_length=80)
    on_failure: str | None = Field(default=None, max_length=80)
    permission: str | None = Field(default=None, max_length=120)
    approval_required: bool = False
    verification: str | None = Field(default=None, max_length=500)


class ProcedureCandidateDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,79}$")
    title: str = Field(min_length=3, max_length=200)
    intent: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=3, max_length=1000)
    visibility: Literal["company", "department", "it_only"] = "it_only"
    department_id: UUID | None = None
    applicability: tuple[ApplicabilitySignal, ...] = Field(min_length=1, max_length=40)
    prerequisites: tuple[str, ...] = Field(default=(), max_length=20)
    steps: tuple[ProcedureStepDefinition, ...] = Field(min_length=1, max_length=40)
    prohibited_actions: tuple[str, ...] = Field(default=(), max_length=20)
    evidence_refs: tuple[str, ...] = Field(min_length=1, max_length=100)
    example_episode_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    source_document_version_id: UUID | None = None
    version_range: str | None = Field(default=None, max_length=120)
    compiled_signature: str = Field(min_length=3, max_length=200)

    @model_validator(mode="after")
    def validate_step_graph(self) -> ProcedureCandidateDefinition:
        if (self.visibility == "department") != (self.department_id is not None):
            raise ValueError("Department procedure visibility requires one department_id")
        keys = [step.step_key for step in self.steps]
        if len(keys) != len(set(keys)):
            raise ValueError("Procedure step keys must be unique")
        known = set(keys)
        for step in self.steps:
            for target in (step.on_success, step.on_failure):
                if target is not None and target not in known:
                    raise ValueError("Procedure transitions must target a step in the same version")
        signals = [(item.signal_type, item.value) for item in self.applicability]
        if len(signals) != len(set(signals)):
            raise ValueError("Procedure applicability signals must be unique")
        return self


class ProcedureReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision: Literal["approve", "reject", "request_changes", "deprecate"]
    notes: str | None = Field(default=None, max_length=1000)
