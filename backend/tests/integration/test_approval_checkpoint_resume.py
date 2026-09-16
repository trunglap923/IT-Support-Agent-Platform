from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.agent.approval_checkpoint import (
    ApprovalCheckpointError,
    pause_ticket_approval,
    resume_ticket_approval,
)
from app.auth.demo_identity import ensure_demo_identity
from app.config import Settings
from app.db import Database
from app.db.models import AgentRun, ApprovalRequest, Conversation, RunKind, RunStatus
from app.main import create_app
from app.services.approvals import ApprovalService, execute_approval_resume_run
from app.tools.schemas import CreateTicketArguments

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


class RecordingDispatcher:
    def __init__(self) -> None:
        self.enqueued: list[UUID] = []

    async def ensure_available(self) -> None:
        return None

    async def enqueue_run(self, run_id: UUID) -> None:
        self.enqueued.append(run_id)


def test_approval_resumes_matching_postgres_checkpoint(
    migrated_database_url: str,
) -> None:
    async def seed() -> tuple[UUID, UUID, str, UUID, str]:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                owner = await ensure_demo_identity(session, password=PASSWORD)
                conversation = Conversation(owner_id=owner.id, title="Checkpoint approval")
                session.add(conversation)
                await session.flush()
                checkpoint_thread_id = f"approval:{uuid4()}"
                run = AgentRun(
                    conversation_id=conversation.id,
                    actor_id=owner.id,
                    kind=RunKind.CHAT,
                    client_request_id="approval-checkpoint",
                    input_hash="e" * 64,
                    status=RunStatus.WAITING_APPROVAL,
                    checkpoint_thread_id=checkpoint_thread_id,
                    prompt_version="test",
                    model="fake",
                )
                session.add(run)
                await session.flush()
                approval = await ApprovalService().create_ticket_draft(
                    session,
                    owner_id=owner.id,
                    run_id=run.id,
                    action_id="checkpoint-action",
                    arguments=CreateTicketArguments(
                        title="Create a VPN ticket",
                        description="VPN remains unavailable after troubleshooting.",
                        issue_type="vpn",
                        severity="normal",
                    ),
                )
                return (
                    owner.id,
                    run.id,
                    checkpoint_thread_id,
                    approval.id,
                    approval.arguments_hash,
                )
        finally:
            await database.close()

    owner_id, run_id, thread_id, approval_id, arguments_hash = asyncio.run(seed())
    pause_ticket_approval(
        database_url=migrated_database_url,
        checkpoint_thread_id=thread_id,
        run_id=run_id,
        actor_id=owner_id,
        approval_id=approval_id,
        arguments_hash=arguments_hash,
    )
    with pytest.raises(ApprovalCheckpointError, match="does not match"):
        resume_ticket_approval(
            database_url=migrated_database_url,
            checkpoint_thread_id=thread_id,
            run_id=run_id,
            actor_id=uuid4(),
            approval_id=approval_id,
            arguments_hash=arguments_hash,
            approved=True,
        )

    settings = Settings(
        database_url=migrated_database_url,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )
    dispatcher = RecordingDispatcher()
    with TestClient(
        create_app(settings=settings, run_dispatcher=dispatcher), base_url=ORIGIN
    ) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        response = client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            json={"decision": "approve", "expected_version": 1},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": login.json()["csrf_token"],
            },
        )
        assert response.status_code == 200
        assert dispatcher.enqueued == [run_id]

    async def resume_and_read() -> tuple[str, RunStatus, str | None, str]:
        database = Database(migrated_database_url)
        try:
            result = await execute_approval_resume_run(database, run_id=run_id)
            async with database.session() as session:
                run = await session.get(AgentRun, run_id)
                approval = await session.get(ApprovalRequest, approval_id)
                assert run is not None and approval is not None
                return result, run.status, run.outcome, approval.status
        finally:
            await database.close()

    result, run_status, outcome, approval_status = asyncio.run(resume_and_read())
    assert result == "resumed"
    assert run_status is RunStatus.COMPLETED
    assert outcome == "ticket_created"
    assert approval_status == "executed"
