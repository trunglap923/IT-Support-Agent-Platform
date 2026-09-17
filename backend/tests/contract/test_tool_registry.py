from __future__ import annotations

import asyncio
from uuid import uuid4

from app.mcp_server.client import discover_business_tools
from app.tools import (
    TOOL_REGISTRY,
    ToolExecutionContext,
    ToolExecutor,
    read_tool_definitions,
    support_tool_definitions,
)


def test_registry_and_mcp_discovery_share_read_contracts() -> None:
    async def scenario() -> None:
        discovered = await discover_business_tools(
            actor_id=uuid4(),
            run_id=uuid4(),
            database_url="postgresql+asyncpg://unused:unused@127.0.0.1/unused",
        )
        for name in ("check_service_status", "get_my_open_tickets"):
            assert discovered[name]["input_schema"] == TOOL_REGISTRY[name].input_schema()

    asyncio.run(scenario())


def test_registry_exposes_only_four_model_capabilities() -> None:
    assert tuple(TOOL_REGISTRY) == (
        "search_knowledge_base",
        "check_service_status",
        "get_my_open_tickets",
        "create_ticket",
    )
    for spec in TOOL_REGISTRY.values():
        properties = spec.input_schema().get("properties", {})
        assert not {"user_id", "role", "sql", "token", "approved"}.intersection(properties)


def test_chat_router_exposes_only_read_tools() -> None:
    assert [item["name"] for item in read_tool_definitions()] == [
        "check_service_status",
        "get_my_open_tickets",
    ]
    assert [item["name"] for item in support_tool_definitions()] == [
        "check_service_status",
        "get_my_open_tickets",
        "create_ticket",
    ]


def test_executor_rejects_untrusted_and_repeated_arguments() -> None:
    async def local_search(query: str, limit: int) -> dict[str, object]:
        return {"query": query, "limit": limit, "results": []}

    async def scenario() -> None:
        executor = ToolExecutor(
            context=ToolExecutionContext(
                actor_id=uuid4(),
                run_id=uuid4(),
                database_url="postgresql+asyncpg://unused:unused@127.0.0.1/unused",
            ),
            local_search=local_search,
        )
        invalid = await executor.execute(
            call_id="call-1",
            name="check_service_status",
            arguments={"service_id": "vpn", "user_id": str(uuid4())},
        )
        first = await executor.execute(
            call_id="call-2",
            name="search_knowledge_base",
            arguments={"query": "reset vpn", "limit": 3},
        )
        repeated = await executor.execute(
            call_id="call-3",
            name="search_knowledge_base",
            arguments={"query": "reset vpn", "limit": 3},
        )
        approval = await executor.execute(
            call_id="call-4",
            name="create_ticket",
            arguments={
                "title": "VPN access issue",
                "description": "VPN fails after following the guide.",
                "issue_type": "vpn",
            },
        )
        assert invalid.error is not None and invalid.error.code == "invalid_arguments"
        assert first.status == "success"
        assert repeated.error is not None and repeated.error.code == "repeated_arguments"
        assert approval.error is not None and approval.error.code == "approval_required"

    asyncio.run(scenario())
