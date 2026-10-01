"""Internal MCP-compatible JSON-RPC server over stdio."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from pydantic import ValidationError

from app.db import Database
from app.mcp_server.context import MCPContextError, load_execution_context
from app.mcp_server.read_tools import (
    check_service_status,
    get_my_open_tickets,
    get_my_profile,
    get_my_recent_tickets,
)
from app.mcp_server.schemas import (
    CurrentUserProfileResult,
    EmptyArguments,
    OpenTicketsResult,
    RecentTicketsResult,
    ServiceStatusArguments,
    ServiceStatusResult,
)
from app.services.service_status import ServiceStatusNotFoundError

SERVER_NAME = "it-support-internal-tools"
SERVER_VERSION = "0.1.0"
READ_TOOL_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "name": "get_my_profile",
        "description": "Read the current authenticated user's display name.",
        "inputSchema": EmptyArguments.model_json_schema(),
    },
    {
        "name": "check_service_status",
        "description": "Read the simulated status of an allowlisted internal service.",
        "inputSchema": ServiceStatusArguments.model_json_schema(),
    },
    {
        "name": "get_my_open_tickets",
        "description": "List at most ten open tickets owned by the current actor.",
        "inputSchema": EmptyArguments.model_json_schema(),
    },
    {
        "name": "get_my_recent_tickets",
        "description": "List at most ten recently updated tickets owned by the current actor.",
        "inputSchema": EmptyArguments.model_json_schema(),
    },
)


def _result(request_id: object, payload: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def _tool_result(request_id: object, payload: dict[str, Any]) -> dict[str, Any]:
    return _result(
        request_id,
        {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "structuredContent": payload,
            "isError": False,
        },
    )


def _tool_error(request_id: object, code: str) -> dict[str, Any]:
    payload = {"ok": False, "error": {"code": code}}
    return _result(
        request_id,
        {
            "content": [{"type": "text", "text": json.dumps(payload)}],
            "structuredContent": payload,
            "isError": True,
        },
    )


async def dispatch(message: dict[str, Any]) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = message.get("method")
    if request_id is None:
        return None
    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
    if method == "tools/list":
        return _result(request_id, {"tools": list(READ_TOOL_DEFINITIONS)})
    if method != "tools/call":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "Method not found"},
        }

    params = message.get("params") or {}
    name = params.get("name")
    raw_arguments = params.get("arguments") or {}
    try:
        context = load_execution_context()
        database = Database(context.database_url)
        try:
            response: (
                CurrentUserProfileResult
                | ServiceStatusResult
                | OpenTicketsResult
                | RecentTicketsResult
            )
            if name == "get_my_profile":
                EmptyArguments.model_validate(raw_arguments)
                response = await get_my_profile(database, context=context)
            elif name == "check_service_status":
                arguments = ServiceStatusArguments.model_validate(raw_arguments)
                response = await check_service_status(
                    database, context=context, service_id=arguments.service_id
                )
            elif name == "get_my_open_tickets":
                EmptyArguments.model_validate(raw_arguments)
                response = await get_my_open_tickets(database, context=context)
            elif name == "get_my_recent_tickets":
                EmptyArguments.model_validate(raw_arguments)
                response = await get_my_recent_tickets(database, context=context)
            else:
                return _tool_error(request_id, "tool_not_allowed")
        finally:
            await database.close()
    except ValidationError:
        return _tool_error(request_id, "invalid_arguments")
    except MCPContextError:
        return _tool_error(request_id, "forbidden")
    except ServiceStatusNotFoundError:
        return _tool_error(request_id, "service_not_found")
    return _tool_result(request_id, response.model_dump(mode="json"))


def main() -> None:
    for line in sys.stdin:
        try:
            response = asyncio.run(dispatch(json.loads(line)))
        except Exception:  # pragma: no cover - do not leak internals over the protocol
            response = _tool_error(None, "internal_error")
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
