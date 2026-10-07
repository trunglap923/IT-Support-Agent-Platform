"""Versioned working-memory state shared by all agent runtime adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

WORKING_MEMORY_SCHEMA_VERSION: Literal["working-memory-v1"] = "working-memory-v1"

WorkingMemoryStatus = Literal[
    "active",
    "waiting_input",
    "waiting_approval",
    "verifying",
    "completed",
    "failed",
    "cancelled",
]
PlanStepKind = Literal["inspect", "retrieve", "diagnose", "action", "verify", "communicate"]
PlanStepStatus = Literal["pending", "running", "succeeded", "failed", "skipped", "blocked"]


class WorkingGoal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: str = Field(min_length=1, max_length=1_000)
    success_criteria: tuple[str, ...] = Field(min_length=1, max_length=12)
    constraints: tuple[str, ...] = Field(default=(), max_length=20)


class WorkingEntities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: UUID
    device_id: UUID | None = None
    service_ids: tuple[str, ...] = Field(default=(), max_length=10)


class WorkingPlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    step_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=240)
    kind: PlanStepKind
    status: PlanStepStatus = "pending"
    depends_on: tuple[str, ...] = Field(default=(), max_length=20)
    tool_name: str | None = Field(default=None, max_length=80)
    requires_approval: bool = False


class WorkingPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(ge=1)
    steps: tuple[WorkingPlanStep, ...] = Field(default=(), max_length=40)

    @model_validator(mode="after")
    def validate_step_graph(self) -> WorkingPlan:
        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Working-memory plan step IDs must be unique")
        known = set(step_ids)
        for step in self.steps:
            if step.step_id in step.depends_on:
                raise ValueError("A plan step cannot depend on itself")
            if not set(step.depends_on).issubset(known):
                raise ValueError("Plan dependencies must reference steps in the same plan")

        dependencies = {step.step_id: step.depends_on for step in self.steps}
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visited:
                return
            if step_id in visiting:
                raise ValueError("Working-memory plan dependencies must be acyclic")
            visiting.add(step_id)
            for dependency in dependencies[step_id]:
                visit(dependency)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in step_ids:
            visit(step_id)
        return self


class WorkingHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    hypothesis_id: str = Field(min_length=1, max_length=80)
    statement: str = Field(min_length=1, max_length=1_000)
    confidence: float = Field(ge=0, le=1)
    status: Literal["active", "supported", "rejected"] = "active"
    evidence_refs: tuple[str, ...] = Field(default=(), max_length=20)


class WorkingObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str = Field(min_length=1, max_length=160)
    source_type: Literal["user", "tool", "knowledge", "system"]
    source_ref: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=2_000)
    raw_artifact_ref: str | None = Field(default=None, max_length=500)
    observed_at: datetime
    reliability: float = Field(ge=0, le=1)
    supersedes: str | None = Field(default=None, max_length=160)


class PendingAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str = Field(min_length=1, max_length=160)
    plan_step_id: str = Field(min_length=1, max_length=80)
    tool_name: str = Field(min_length=1, max_length=80)
    arguments_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    requires_approval: bool


class VerificationRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    requirement_id: str = Field(min_length=1, max_length=80)
    statement: str = Field(min_length=1, max_length=500)
    status: Literal["pending", "satisfied", "failed"] = "pending"
    evidence_refs: tuple[str, ...] = Field(default=(), max_length=20)


class WorkingCompactionState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    last_compacted_event_sequence: int = Field(default=0, ge=0)
    summary_version: int = Field(default=0, ge=0)
    summary: str | None = Field(default=None, max_length=8_000)
    source_event_ids: tuple[str, ...] = Field(default=(), max_length=200)


class WorkingCounters(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model_calls: int = Field(default=0, ge=0)
    tool_calls: int = Field(default=0, ge=0)
    retrieval_calls: int = Field(default=0, ge=0)


class WorkingMemorySnapshot(BaseModel):
    """Complete durable task state, distinct from the selected active context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["working-memory-v1"] = WORKING_MEMORY_SCHEMA_VERSION
    working_memory_id: UUID
    tenant_id: UUID | None = None
    run_id: UUID
    conversation_id: UUID
    owner_id: UUID
    ticket_id: UUID | None = None
    incident_key: str | None = Field(default=None, max_length=160)
    status: WorkingMemoryStatus
    goal: WorkingGoal
    entities: WorkingEntities
    plan: WorkingPlan
    hypotheses: tuple[WorkingHypothesis, ...] = Field(default=(), max_length=20)
    observations: tuple[WorkingObservation, ...] = Field(default=(), max_length=100)
    pending_actions: tuple[PendingAction, ...] = Field(default=(), max_length=10)
    verification_requirements: tuple[VerificationRequirement, ...] = Field(
        default=(), max_length=20
    )
    compaction: WorkingCompactionState = WorkingCompactionState()
    counters: WorkingCounters = WorkingCounters()
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_snapshot_invariants(self) -> WorkingMemorySnapshot:
        if self.entities.user_id != self.owner_id:
            raise ValueError("Working-memory user entity must match its owner")
        if self.updated_at < self.created_at:
            raise ValueError("Working-memory update time cannot precede creation time")
        step_ids = {step.step_id for step in self.plan.steps}
        if any(action.plan_step_id not in step_ids for action in self.pending_actions):
            raise ValueError("Pending actions must reference a current plan step")
        if self.status == "waiting_approval" and not any(
            action.requires_approval for action in self.pending_actions
        ):
            raise ValueError("Waiting-approval state requires a pending approval action")
        return self
