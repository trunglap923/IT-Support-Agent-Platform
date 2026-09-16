"""Strict argument schemas exposed to the support model."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.mcp_server.schemas import EmptyArguments, ServiceStatusArguments


class SearchKnowledgeArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=500)
    limit: int = Field(default=5, ge=1, le=8)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        return " ".join(value.split())


class CreateTicketArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=5, max_length=160)
    description: str = Field(min_length=10, max_length=4_000)
    issue_type: Literal["vpn", "docker", "gitlab", "other"]
    severity: Literal["low", "normal", "high"] = "normal"
    device_id: UUID | None = None

    @field_validator("title", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


__all__ = [
    "CreateTicketArguments",
    "EmptyArguments",
    "SearchKnowledgeArguments",
    "ServiceStatusArguments",
]
