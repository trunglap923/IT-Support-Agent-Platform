"""Versioned contracts for auditable long-term memory decisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

MEMORY_DECISION_SCHEMA_VERSION: Literal["memory-decision-v1"] = "memory-decision-v1"
MEMORY_MUTATION_PROPOSAL_SCHEMA_VERSION: Literal["memory-mutation-proposal-v1"] = (
    "memory-mutation-proposal-v1"
)

MemoryOperation = Literal["add", "update", "delete", "noop"]
MemorySourceType = Literal[
    "cmdb",
    "idp",
    "mdm",
    "tool",
    "user_confirmed",
    "ticket",
    "ai_inferred",
]


class MemorySourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: MemorySourceType
    source_ref: str = Field(min_length=1, max_length=500)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    authority_tier: int = Field(ge=0, le=100)


class MemoryMutationProposal(BaseModel):
    """A model/rule proposal. It grants no permission and performs no write."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["memory-mutation-proposal-v1"] = MEMORY_MUTATION_PROPOSAL_SCHEMA_VERSION
    proposal_id: UUID
    owner_id: UUID
    operation: MemoryOperation
    target_memory_id: UUID | None = None
    subject_type: Literal["user", "device", "account", "service"]
    subject_id: str = Field(min_length=1, max_length=160)
    predicate: str = Field(min_length=1, max_length=120)
    proposed_value: dict[str, Any] | None = None
    evidence: tuple[MemorySourceReference, ...] = Field(min_length=1, max_length=20)
    confidence: float = Field(ge=0, le=1)
    reason_code: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_operation_shape(self) -> MemoryMutationProposal:
        if self.operation == "add":
            if self.target_memory_id is not None or self.proposed_value is None:
                raise ValueError("ADD requires a value and cannot target an existing memory")
        elif self.operation == "update":
            if self.target_memory_id is None or self.proposed_value is None:
                raise ValueError("UPDATE requires a target memory and a value")
        elif self.operation == "delete":
            if self.target_memory_id is None or self.proposed_value is not None:
                raise ValueError("DELETE requires only a target memory")
        elif self.proposed_value is not None:
            raise ValueError("NOOP cannot propose a new value")
        return self


class MemoryDecisionRecord(BaseModel):
    """Outcome after deterministic validation and any required human gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["memory-decision-v1"] = MEMORY_DECISION_SCHEMA_VERSION
    decision_id: UUID
    proposal_id: UUID
    owner_id: UUID
    operation: MemoryOperation
    status: Literal["accepted", "rejected", "quarantined"]
    decided_by_type: Literal["system", "user", "it_reviewer", "connector"]
    decided_by_id: UUID | None = None
    policy_version: str = Field(min_length=1, max_length=80)
    reason_code: str = Field(min_length=1, max_length=80)
    resulting_memory_id: UUID | None = None
    decided_at: datetime

    @model_validator(mode="after")
    def validate_decision_shape(self) -> MemoryDecisionRecord:
        if self.status == "accepted":
            if self.operation in {"add", "update"} and self.resulting_memory_id is None:
                raise ValueError("Accepted ADD/UPDATE decisions require a resulting memory ID")
            if self.operation in {"delete", "noop"} and self.resulting_memory_id is not None:
                raise ValueError("Accepted DELETE/NOOP decisions cannot produce a memory ID")
        elif self.resulting_memory_id is not None:
            raise ValueError("Rejected or quarantined decisions cannot produce a memory")
        if self.decided_by_type == "system" and self.decided_by_id is not None:
            raise ValueError("System decisions cannot carry a human or connector actor ID")
        if self.decided_by_type != "system" and self.decided_by_id is None:
            raise ValueError("Non-system decisions require an actor ID")
        return self
