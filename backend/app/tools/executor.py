"""Allowlisted, bounded execution of server-controlled tool calls."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.mcp_server.client import call_business_tool
from app.tools.registry import TOOL_REGISTRY
from app.tools.results import ToolError, ToolResult

LocalSearch = Callable[[str, int], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class ToolExecutionContext:
    actor_id: UUID
    run_id: UUID
    database_url: str


@dataclass(slots=True)
class ToolExecutor:
    context: ToolExecutionContext
    local_search: LocalSearch
    timeout_seconds: float = 5.0
    max_result_bytes: int = 32_000
    _executed_arguments: set[str] = field(default_factory=set, init=False)

    async def execute(self, *, call_id: str, name: str, arguments: dict[str, Any]) -> ToolResult:
        spec = TOOL_REGISTRY.get(name)
        if spec is None:
            return self._failed(call_id, name, "tool_not_allowed")
        try:
            validated = spec.arguments_model.model_validate(arguments)
        except ValidationError:
            return self._failed(call_id, name, "invalid_arguments")

        fingerprint = json.dumps(
            {"name": name, "arguments": validated.model_dump(mode="json")},
            sort_keys=True,
            separators=(",", ":"),
        )
        if fingerprint in self._executed_arguments:
            return self._failed(call_id, name, "repeated_arguments")
        self._executed_arguments.add(fingerprint)

        if spec.route == "approval":
            return self._failed(call_id, name, "approval_required")
        try:
            async with asyncio.timeout(self.timeout_seconds):
                if spec.route == "local":
                    values = validated.model_dump()
                    payload = await self.local_search(values["query"], values["limit"])
                    is_error = False
                else:
                    is_error, payload = await call_business_tool(
                        actor_id=self.context.actor_id,
                        run_id=self.context.run_id,
                        database_url=self.context.database_url,
                        name=name,
                        arguments=validated.model_dump(mode="json"),
                    )
        except TimeoutError:
            return ToolResult(
                call_id=call_id,
                name=name,
                status="unknown",
                error=ToolError(code="timeout", retryable=True),
            )
        if is_error:
            code = str(payload.get("error", {}).get("code", "tool_failed"))
            return self._failed(call_id, name, code)
        if len(json.dumps(payload, ensure_ascii=False).encode()) > self.max_result_bytes:
            return self._failed(call_id, name, "result_too_large")
        return ToolResult(call_id=call_id, name=name, status="success", data=payload)

    @staticmethod
    def _failed(call_id: str, name: str, code: str) -> ToolResult:
        return ToolResult(
            call_id=call_id,
            name=name,
            status="failed",
            error=ToolError(code=code),
        )
