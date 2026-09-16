from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.auth.demo_identity import ensure_demo_identity
from app.auth.passwords import hash_password
from app.config import Settings
from app.db import Database
from app.db.models import AgentRun, Conversation, RunKind, RunStatus, User, UserRole
from app.main import create_app
from app.services.approvals import ApprovalService, canonical_argument_hash
from app.tools.schemas import CreateTicketArguments

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


def test_canonical_argument_hash_is_order_independent() -> None:
    first, first_hash = canonical_argument_hash({"b": 2, "a": "one"})
    second, second_hash = canonical_argument_hash({"a": "one", "b": 2})
    assert first == second == {"a": "one", "b": 2}
    assert first_hash == second_hash


def test_approval_api_enforces_owner_csrf_expiry_and_single_decision(
    migrated_database_url: str,
) -> None:
    async def seed() -> tuple[UUID, UUID, UUID]:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                owner = await ensure_demo_identity(session, password=PASSWORD)
                conversation = Conversation(owner_id=owner.id, title="Approval")
                session.add(conversation)
                await session.flush()
                run = AgentRun(
                    conversation_id=conversation.id,
                    actor_id=owner.id,
                    kind=RunKind.CHAT,
                    client_request_id="approval-owner",
                    input_hash="c" * 64,
                    status=RunStatus.WAITING_APPROVAL,
                    checkpoint_thread_id=f"run:{uuid4()}",
                    prompt_version="test",
                    model="fake",
                )
                session.add(run)
                await session.flush()
                arguments = CreateTicketArguments(
                    title="VPN still unavailable",
                    description="VPN remains unavailable after following the guide.",
                    issue_type="vpn",
                    severity="normal",
                )
                service = ApprovalService()
                active = await service.create_ticket_draft(
                    session,
                    owner_id=owner.id,
                    run_id=run.id,
                    action_id="action-active",
                    arguments=arguments,
                )
                expired = await service.create_ticket_draft(
                    session,
                    owner_id=owner.id,
                    run_id=run.id,
                    action_id="action-expired",
                    arguments=arguments,
                    now=datetime.now(UTC) - timedelta(minutes=16),
                )

                outsider = User(
                    email="approval-outsider@example.com",
                    display_name="Outsider",
                    password_hash=hash_password(PASSWORD),
                    role=UserRole.EMPLOYEE,
                    department_id=owner.department_id,
                    active=True,
                )
                session.add(outsider)
                await session.flush()
                outsider_conversation = Conversation(owner_id=outsider.id, title="Private")
                session.add(outsider_conversation)
                await session.flush()
                outsider_run = AgentRun(
                    conversation_id=outsider_conversation.id,
                    actor_id=outsider.id,
                    kind=RunKind.CHAT,
                    client_request_id="approval-outsider",
                    input_hash="d" * 64,
                    status=RunStatus.WAITING_APPROVAL,
                    checkpoint_thread_id=f"run:{uuid4()}",
                    prompt_version="test",
                    model="fake",
                )
                session.add(outsider_run)
                await session.flush()
                outsider_approval = await service.create_ticket_draft(
                    session,
                    owner_id=outsider.id,
                    run_id=outsider_run.id,
                    action_id="action-outsider",
                    arguments=arguments,
                )
                return active.id, expired.id, outsider_approval.id
        finally:
            await database.close()

    active_id, expired_id, outsider_id = asyncio.run(seed())
    settings = Settings(
        database_url=migrated_database_url,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )
    with TestClient(create_app(settings=settings), base_url=ORIGIN) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        csrf = login.json()["csrf_token"]
        assert client.get(f"/api/v1/approvals/{outsider_id}").status_code == 404
        assert (
            client.post(
                f"/api/v1/approvals/{active_id}/decision",
                json={"decision": "approve", "expected_version": 1},
                headers={"Origin": ORIGIN},
            ).status_code
            == 403
        )
        approved = client.post(
            f"/api/v1/approvals/{active_id}/decision",
            json={"decision": "approve", "expected_version": 1},
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["version"] == 2
        replay = client.post(
            f"/api/v1/approvals/{active_id}/decision",
            json={"decision": "approve", "expected_version": 1},
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        assert replay.status_code == 409
        expired = client.post(
            f"/api/v1/approvals/{expired_id}/decision",
            json={"decision": "reject", "expected_version": 1},
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        )
        assert expired.status_code == 409
        assert client.get(f"/api/v1/approvals/{expired_id}").json()["status"] == "expired"
