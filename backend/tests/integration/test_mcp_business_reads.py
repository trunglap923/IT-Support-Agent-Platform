from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from app.auth.passwords import hash_password
from app.db import Database
from app.db.models import (
    AgentRun,
    Conversation,
    Department,
    RunKind,
    RunStatus,
    Ticket,
    User,
    UserRole,
)
from app.mcp_server.client import call_business_tool, discover_business_tools
from app.services.service_status import ServiceStatusService


def test_mcp_stdio_reads_revalidate_actor_and_preserve_ownership(
    migrated_database_url: str,
) -> None:
    async def seed() -> tuple[UUID, UUID, UUID, UUID]:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                department = Department(key="engineering", name="Engineering")
                session.add(department)
                await session.flush()
                alice = User(
                    email="alice-mcp@example.com",
                    display_name="Alice",
                    password_hash=hash_password("test-password"),
                    role=UserRole.EMPLOYEE,
                    department_id=department.id,
                    active=True,
                )
                bob = User(
                    email="bob-mcp@example.com",
                    display_name="Bob",
                    password_hash=hash_password("test-password"),
                    role=UserRole.EMPLOYEE,
                    department_id=department.id,
                    active=True,
                )
                session.add_all([alice, bob])
                await session.flush()
                alice_conversation = Conversation(owner_id=alice.id, title="Alice support")
                bob_conversation = Conversation(owner_id=bob.id, title="Bob support")
                session.add_all([alice_conversation, bob_conversation])
                await session.flush()
                alice_run = AgentRun(
                    conversation_id=alice_conversation.id,
                    actor_id=alice.id,
                    kind=RunKind.CHAT,
                    client_request_id="mcp-alice",
                    input_hash="a" * 64,
                    status=RunStatus.COMPLETED,
                    outcome="answered",
                    checkpoint_thread_id=f"run:{uuid4()}",
                    prompt_version="test",
                    model="fake",
                    finished_at=alice_conversation.created_at,
                )
                bob_run = AgentRun(
                    conversation_id=bob_conversation.id,
                    actor_id=bob.id,
                    kind=RunKind.CHAT,
                    client_request_id="mcp-bob",
                    input_hash="b" * 64,
                    status=RunStatus.COMPLETED,
                    outcome="answered",
                    checkpoint_thread_id=f"run:{uuid4()}",
                    prompt_version="test",
                    model="fake",
                    finished_at=bob_conversation.created_at,
                )
                session.add_all([alice_run, bob_run])
                await session.flush()
                session.add_all(
                    [
                        Ticket(
                            display_key="IT-MCP-A",
                            owner_id=alice.id,
                            department_id=department.id,
                            title="Alice VPN",
                            description="Alice cannot connect to the VPN.",
                            issue_type="vpn",
                            severity="normal",
                            status="open",
                        ),
                        Ticket(
                            display_key="IT-MCP-B",
                            owner_id=bob.id,
                            department_id=department.id,
                            title="Bob GitLab",
                            description="Bob cannot open the GitLab project.",
                            issue_type="gitlab",
                            severity="low",
                            status="open",
                        ),
                    ]
                )
                await ServiceStatusService().ensure_defaults(session)
                return alice.id, alice_run.id, bob.id, bob_run.id
        finally:
            await database.close()

    async def scenario() -> None:
        alice_id, alice_run_id, bob_id, bob_run_id = await seed()
        discovered = await discover_business_tools(
            actor_id=alice_id,
            run_id=alice_run_id,
            database_url=migrated_database_url,
        )
        assert set(discovered) == {"check_service_status", "get_my_open_tickets"}

        alice_result, bob_result = await asyncio.gather(
            call_business_tool(
                actor_id=alice_id,
                run_id=alice_run_id,
                database_url=migrated_database_url,
                name="get_my_open_tickets",
                arguments={},
            ),
            call_business_tool(
                actor_id=bob_id,
                run_id=bob_run_id,
                database_url=migrated_database_url,
                name="get_my_open_tickets",
                arguments={},
            ),
        )
        assert alice_result[0] is False
        assert [item["display_key"] for item in alice_result[1]["tickets"]] == ["IT-MCP-A"]
        assert [item["display_key"] for item in bob_result[1]["tickets"]] == ["IT-MCP-B"]

        is_error, forbidden = await call_business_tool(
            actor_id=bob_id,
            run_id=alice_run_id,
            database_url=migrated_database_url,
            name="check_service_status",
            arguments={"service_id": "vpn"},
        )
        assert is_error is True
        assert forbidden["error"]["code"] == "forbidden"

    asyncio.run(scenario())
