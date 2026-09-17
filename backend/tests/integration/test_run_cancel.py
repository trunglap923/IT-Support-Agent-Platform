from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.auth.demo_identity import ensure_demo_identity
from app.config import Settings
from app.db import Database
from app.db.models import AgentRun, ApprovalStatus, Conversation, RunKind, RunStatus
from app.main import create_app
from app.services.approvals.service import ApprovalService
from app.tools.schemas import CreateTicketArguments

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


def test_owner_cancel_is_csrf_protected_versioned_and_idempotent(
    migrated_database_url: str,
) -> None:
    async def seed() -> tuple[UUID, UUID, UUID, UUID]:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                owner = await ensure_demo_identity(session, password=PASSWORD)
                run_ids: list[UUID] = []
                for index, run_status in enumerate(
                    (RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.WAITING_APPROVAL)
                ):
                    conversation = Conversation(owner_id=owner.id, title=f"Cancel {index}")
                    session.add(conversation)
                    await session.flush()
                    run = AgentRun(
                        conversation_id=conversation.id,
                        actor_id=owner.id,
                        kind=RunKind.CHAT,
                        client_request_id=f"cancel-run-{index}",
                        input_hash=str(index) * 64,
                        status=run_status,
                        checkpoint_thread_id=f"run:{uuid4()}",
                        prompt_version="test",
                        model="fake",
                    )
                    session.add(run)
                    await session.flush()
                    run_ids.append(run.id)
                approval = await ApprovalService().create_ticket_draft(
                    session,
                    owner_id=owner.id,
                    run_id=run_ids[2],
                    action_id="cancel-waiting-approval",
                    arguments=CreateTicketArguments(
                        title="VPN certificate warning",
                        description="The managed Ubuntu device reports a VPN certificate warning.",
                        issue_type="vpn",
                    ),
                )
                return run_ids[0], run_ids[1], run_ids[2], approval.id
        finally:
            await database.close()

    queued_id, running_id, waiting_id, approval_id = asyncio.run(seed())
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
        headers = {"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]}
        assert (
            client.post(
                f"/api/v1/runs/{queued_id}/cancel",
                json={"expected_version": 1},
                headers={"Origin": ORIGIN},
            ).status_code
            == 403
        )
        stale = client.post(
            f"/api/v1/runs/{queued_id}/cancel",
            json={"expected_version": 99},
            headers=headers,
        )
        assert stale.status_code == 409
        cancelled = client.post(
            f"/api/v1/runs/{queued_id}/cancel",
            json={"expected_version": 1},
            headers=headers,
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        assert cancelled.json()["outcome"] == "cancelled_by_user"
        replay = client.post(
            f"/api/v1/runs/{queued_id}/cancel",
            json={"expected_version": 1},
            headers=headers,
        )
        assert replay.status_code == 200
        assert replay.json()["version"] == cancelled.json()["version"]
        running = client.post(
            f"/api/v1/runs/{running_id}/cancel",
            json={"expected_version": 1},
            headers=headers,
        )
        assert running.status_code == 409
        waiting = client.post(
            f"/api/v1/runs/{waiting_id}/cancel",
            json={"expected_version": 1},
            headers=headers,
        )
        assert waiting.status_code == 200
        assert waiting.json()["status"] == "cancelled"
        approval = client.get(f"/api/v1/approvals/{approval_id}")
        assert approval.status_code == 200
        assert approval.json()["status"] == ApprovalStatus.EXPIRED.value
        assert approval.json()["version"] == 2
