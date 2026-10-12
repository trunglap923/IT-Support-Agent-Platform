"""Single source of truth for model-visible tool schemas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from app.mcp_server.schemas import (
    CurrentUserProfileResult,
    OpenTicketsResult,
    RecentTicketsResult,
    ServiceStatusResult,
)
from app.tools.schemas import (
    CreateTicketArguments,
    EmptyArguments,
    SearchKnowledgeArguments,
    SearchKnowledgeResult,
    ServiceStatusArguments,
)

ToolRoute = Literal["local", "mcp_read", "approval"]
ToolRisk = Literal["low", "medium", "high"]
ApprovalPolicy = Literal["never", "always"]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    arguments_model: type[BaseModel]
    route: ToolRoute
    output_model: type[BaseModel] | None = None
    allowed_roles: frozenset[str] = frozenset({"employee", "it", "admin"})
    risk_level: ToolRisk = "low"
    approval_policy: ApprovalPolicy = "never"
    timeout_seconds: float = 5.0
    max_attempts: int = 1

    def input_schema(self) -> dict[str, object]:
        return self.arguments_model.model_json_schema()

    def model_definition(self) -> dict[str, object]:
        parameters = self.input_schema()
        properties = parameters.get("properties")
        if isinstance(properties, dict):
            parameters["required"] = list(properties)
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": parameters,
            "strict": True,
        }


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_knowledge_base": ToolSpec(
        name="search_knowledge_base",
        description="Search approved IT documentation visible to the current user.",
        arguments_model=SearchKnowledgeArguments,
        route="local",
        output_model=SearchKnowledgeResult,
    ),
    "get_my_profile": ToolSpec(
        name="get_my_profile",
        description=(
            "Read the current authenticated user's display name when they ask who they are "
            "or what their name is."
        ),
        arguments_model=EmptyArguments,
        route="mcp_read",
        output_model=CurrentUserProfileResult,
    ),
    "check_service_status": ToolSpec(
        name="check_service_status",
        description="Read the simulated status of an allowlisted internal service.",
        arguments_model=ServiceStatusArguments,
        route="mcp_read",
        output_model=ServiceStatusResult,
    ),
    "get_my_open_tickets": ToolSpec(
        name="get_my_open_tickets",
        description="List at most ten open tickets owned by the current user.",
        arguments_model=EmptyArguments,
        route="mcp_read",
        output_model=OpenTicketsResult,
    ),
    "get_my_recent_tickets": ToolSpec(
        name="get_my_recent_tickets",
        description=(
            "List at most ten recently updated tickets owned by the current user, "
            "including resolved tickets."
        ),
        arguments_model=EmptyArguments,
        route="mcp_read",
        output_model=RecentTicketsResult,
    ),
    "create_ticket": ToolSpec(
        name="create_ticket",
        description=(
            "Prepare a ticket draft from the current request and relevant conversation context. "
            "A linked device is optional; leave device_id empty when unavailable. The draft "
            "requires explicit user approval before ticket creation."
        ),
        arguments_model=CreateTicketArguments,
        route="approval",
        risk_level="medium",
        approval_policy="always",
    ),
}


def model_tool_definitions() -> list[dict[str, object]]:
    return [spec.model_definition() for spec in TOOL_REGISTRY.values()]


def read_tool_definitions() -> list[dict[str, object]]:
    """Return only side-effect-free business reads available during chat routing."""

    return [spec.model_definition() for spec in TOOL_REGISTRY.values() if spec.route == "mcp_read"]


def support_tool_definitions() -> list[dict[str, object]]:
    """Tools selectable by chat; execution still enforces read/approval routes."""

    return [
        spec.model_definition()
        for spec in TOOL_REGISTRY.values()
        if spec.route in {"mcp_read", "approval"}
    ]
