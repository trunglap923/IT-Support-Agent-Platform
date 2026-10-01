"""Strict schemas exposed by internal MCP read tools."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmptyArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ServiceStatusArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_id: Literal["vpn", "registry", "gitlab"]


class ServiceStatusResult(BaseModel):
    service_id: str
    status: Literal["healthy", "degraded", "down", "unknown"]
    message: str
    updated_at: datetime


class CurrentUserProfileResult(BaseModel):
    display_name: str


class TicketSummary(BaseModel):
    id: UUID
    display_key: str
    title: str
    issue_type: str
    severity: str
    status: str
    updated_at: datetime


class OpenTicketsResult(BaseModel):
    tickets: list[TicketSummary] = Field(max_length=10)


class RecentTicketsResult(BaseModel):
    tickets: list[TicketSummary] = Field(max_length=10)
