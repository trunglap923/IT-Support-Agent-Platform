"""Shared, allowlisted memory contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryKind = Literal["profile", "preference", "device"]
MemoryKey = Literal["preferred_language", "operating_system", "device_label"]

KEY_KIND: dict[MemoryKey, MemoryKind] = {
    "preferred_language": "preference",
    "operating_system": "device",
    "device_label": "device",
}


class CandidateProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: MemoryKind
    key: MemoryKey
    value: str = Field(min_length=1, max_length=240)
    evidence: str = Field(min_length=1, max_length=500)
