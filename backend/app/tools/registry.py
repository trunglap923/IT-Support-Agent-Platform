"""Single source of truth for model-visible tool schemas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from app.tools.schemas import (
    CreateTicketArguments,
    EmptyArguments,
    SearchKnowledgeArguments,
    ServiceStatusArguments,
)

ToolRoute = Literal["local", "mcp_read", "approval"]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    arguments_model: type[BaseModel]
    route: ToolRoute

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
    ),
    "get_my_profile": ToolSpec(
        name="get_my_profile",
        description=(
            "Read the current authenticated user's display name when they ask who they are "
            "or what their name is."
        ),
        arguments_model=EmptyArguments,
        route="mcp_read",
    ),
    "check_service_status": ToolSpec(
        name="check_service_status",
        description="Read the simulated status of an allowlisted internal service.",
        arguments_model=ServiceStatusArguments,
        route="mcp_read",
    ),
    "get_my_open_tickets": ToolSpec(
        name="get_my_open_tickets",
        description="List at most ten open tickets owned by the current user.",
        arguments_model=EmptyArguments,
        route="mcp_read",
    ),
    "get_my_recent_tickets": ToolSpec(
        name="get_my_recent_tickets",
        description=(
            "List at most ten recently updated tickets owned by the current user, "
            "including resolved tickets."
        ),
        arguments_model=EmptyArguments,
        route="mcp_read",
    ),
    "create_ticket": ToolSpec(
        name="create_ticket",
        description="Draft a support ticket that requires explicit user approval before creation.",
        arguments_model=CreateTicketArguments,
        route="approval",
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
