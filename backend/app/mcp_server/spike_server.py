"""Minimal stdio MCP server used to prove subprocess actor isolation."""

from __future__ import annotations

import os

from mcp.server import MCPServer

from app.mcp_server.spike_models import ActorContext, ActorIdentity

ACTOR_ENV = "MCP_ACTOR_ID"
RUN_ENV = "MCP_RUN_ID"
SENSITIVE_ENV_NAMES = (
    "OPENAI_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "DATABASE_URL",
)


def load_actor_context() -> ActorContext:
    actor_id = os.getenv(ACTOR_ENV, "").strip()
    run_id = os.getenv(RUN_ENV, "").strip()
    if not actor_id or not run_id:
        raise RuntimeError(f"{ACTOR_ENV} and {RUN_ENV} are required")
    return ActorContext(actor_id=actor_id, run_id=run_id)


actor_context = load_actor_context()
mcp = MCPServer(
    "it-support-actor-isolation-spike",
    instructions="Expose only the trusted actor context injected for this subprocess.",
    log_level="ERROR",
)


@mcp.tool()
def current_actor() -> ActorIdentity:
    """Return the actor and run bound to this isolated execution segment."""

    return ActorIdentity(
        actor_id=actor_context.actor_id,
        run_id=actor_context.run_id,
        sensitive_environment_present=[
            name for name in SENSITIVE_ENV_NAMES if os.getenv(name) is not None
        ],
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
