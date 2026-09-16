"""Minimal MCP stdio server used to prove subprocess actor isolation."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

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


def current_actor(context: ActorContext) -> ActorIdentity:
    return ActorIdentity(
        actor_id=context.actor_id,
        run_id=context.run_id,
        sensitive_environment_present=[
            name for name in SENSITIVE_ENV_NAMES if os.getenv(name) is not None
        ],
    )


def _response(request_id: object, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def dispatch(message: dict[str, Any], context: ActorContext) -> dict[str, Any] | None:
    request_id = message.get("id")
    method = message.get("method")
    if request_id is None:
        return None
    if method == "initialize":
        return _response(
            request_id,
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "it-support-actor-isolation-spike", "version": "0.1.0"},
            },
        )
    if method == "tools/list":
        return _response(
            request_id,
            {
                "tools": [
                    {
                        "name": "current_actor",
                        "description": "Return the trusted actor bound to this subprocess.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False,
                        },
                        "outputSchema": {
                            "type": "object",
                            "properties": {
                                "actor_id": {"type": "string"},
                                "run_id": {"type": "string"},
                                "sensitive_environment_present": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["actor_id", "run_id", "sensitive_environment_present"],
                        },
                    }
                ]
            },
        )
    if method == "tools/call" and message.get("params", {}).get("name") == "current_actor":
        payload = current_actor(context).model_dump(mode="json")
        return _response(
            request_id,
            {
                "content": [{"type": "text", "text": json.dumps(payload)}],
                "structuredContent": payload,
                "isError": False,
            },
        )
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "Method not found"},
    }


def main() -> None:
    context = load_actor_context()
    for line in sys.stdin:
        try:
            response = dispatch(json.loads(line), context)
        except Exception as exc:  # pragma: no cover - defensive protocol boundary
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": type(exc).__name__},
            }
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
