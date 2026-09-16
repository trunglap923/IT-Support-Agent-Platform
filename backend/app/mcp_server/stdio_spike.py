"""Client-side probe for MCP discovery, calls and actor isolation over stdio."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.mcp_server.spike_models import ActorIdentity


@dataclass(frozen=True, slots=True)
class MCPActorProbe:
    actor_id: str
    run_id: str
    discovered_tools: tuple[str, ...]
    sensitive_environment_present: tuple[str, ...]


def isolated_server_environment(*, actor_id: str, run_id: str) -> dict[str, str]:
    """Build an allowlist instead of inheriting worker/provider credentials."""

    return {
        "MCP_ACTOR_ID": actor_id,
        "MCP_RUN_ID": run_id,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }


async def probe_actor(*, actor_id: str, run_id: str) -> MCPActorProbe:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server.spike_server"],
        env=isolated_server_environment(actor_id=actor_id, run_id=run_id),
        cwd=Path(__file__).resolve().parents[2],
    )
    async with (
        stdio_client(parameters) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as client,
    ):
        await client.initialize()
        listed = await client.list_tools()
        discovered_tools = tuple(tool.name for tool in listed.tools)
        result = await client.call_tool("current_actor", {})

    if result.is_error or result.structured_content is None:
        raise RuntimeError("MCP current_actor returned an error or no structured content")
    identity = ActorIdentity.model_validate(result.structured_content)
    return MCPActorProbe(
        actor_id=identity.actor_id,
        run_id=identity.run_id,
        discovered_tools=discovered_tools,
        sensitive_environment_present=tuple(identity.sensitive_environment_present),
    )


async def run_stdio_isolation_spike() -> tuple[MCPActorProbe, MCPActorProbe]:
    first, second = await asyncio.gather(
        probe_actor(actor_id="user-alice", run_id="run-alice-001"),
        probe_actor(actor_id="user-bob", run_id="run-bob-001"),
    )
    if first.actor_id == second.actor_id or first.run_id == second.run_id:
        raise RuntimeError("MCP subprocess actor contexts were not isolated")
    return first, second


async def async_main() -> None:
    probes = await run_stdio_isolation_spike()
    print(json.dumps([asdict(probe) for probe in probes], ensure_ascii=False, indent=2))


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
