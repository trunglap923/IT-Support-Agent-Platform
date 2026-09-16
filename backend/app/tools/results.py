"""Bounded result envelope returned to the orchestration layer."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ToolError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    retryable: bool = False


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    call_id: str
    name: str
    status: Literal["success", "failed", "unknown"]
    data: dict[str, Any] | None = None
    error: ToolError | None = None
