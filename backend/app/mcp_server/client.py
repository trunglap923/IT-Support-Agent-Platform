"""Short-lived stdio client for internal MCP tools."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def isolated_business_environment(
    *, actor_id: UUID, run_id: UUID, database_url: str
) -> dict[str, str]:
    return {
        "MCP_ACTOR_ID": str(actor_id),
        "MCP_RUN_ID": str(run_id),
        "MCP_DATABASE_URL": database_url,
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }


def server_parameters(*, actor_id: UUID, run_id: UUID, database_url: str) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server"],
        env=isolated_business_environment(
            actor_id=actor_id, run_id=run_id, database_url=database_url
        ),
        cwd=Path(__file__).resolve().parents[2],
    )


async def discover_business_tools(
    *, actor_id: UUID, run_id: UUID, database_url: str
) -> dict[str, dict[str, Any]]:
    parameters = server_parameters(actor_id=actor_id, run_id=run_id, database_url=database_url)
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as client,
    ):
        await client.initialize()
        listed = await client.list_tools()
    return {
        tool.name: {
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in listed.tools
    }


async def call_business_tool(
    *,
    actor_id: UUID,
    run_id: UUID,
    database_url: str,
    name: str,
    arguments: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    parameters = server_parameters(actor_id=actor_id, run_id=run_id, database_url=database_url)
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as client,
    ):
        await client.initialize()
        result = await client.call_tool(name, arguments)
    if result.structured_content is not None:
        payload = result.structured_content
    elif result.content and hasattr(result.content[0], "text"):
        payload = json.loads(result.content[0].text)
    else:
        payload = {}
    return bool(result.is_error), payload
