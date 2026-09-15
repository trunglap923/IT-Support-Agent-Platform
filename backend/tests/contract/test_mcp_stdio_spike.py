import asyncio

from app.mcp_server.stdio_spike import (
    isolated_server_environment,
    run_stdio_isolation_spike,
)


def test_stdio_discovery_call_and_actor_isolation(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-subprocess")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "must-not-reach-subprocess")

    first, second = asyncio.run(run_stdio_isolation_spike())

    assert first.actor_id == "user-alice"
    assert first.run_id == "run-alice-001"
    assert second.actor_id == "user-bob"
    assert second.run_id == "run-bob-001"
    assert first.discovered_tools == ("current_actor",)
    assert second.discovered_tools == ("current_actor",)
    assert first.sensitive_environment_present == ()
    assert second.sensitive_environment_present == ()


def test_subprocess_environment_is_an_allowlist() -> None:
    environment = isolated_server_environment(actor_id="user-a", run_id="run-a")

    assert environment["MCP_ACTOR_ID"] == "user-a"
    assert environment["MCP_RUN_ID"] == "run-a"
    assert "OPENAI_API_KEY" not in environment
    assert "DATABASE_URL" not in environment
