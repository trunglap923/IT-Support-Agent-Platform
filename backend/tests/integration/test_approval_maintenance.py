from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.auth.demo_identity import ensure_demo_identity
from app.db import Database
from app.db.models import (
    AgentRun,
    ApprovalRequest,
    ApprovalStatus,
    Conversation,
    RunEvent,
    RunKind,
    RunStatus,
)
from app.jobs.maintenance import expire_pending_approvals
from app.services.approvals import ApprovalService
from app.tools.schemas import CreateTicketArguments

PASSWORD = "correct-horse-battery-staple"


def test_expiry_job_is_atomic_bounded_and_idempotent(migrated_database_url: str) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            now = datetime.now(UTC)
            async with database.session() as session, session.begin():
                owner = await ensure_demo_identity(session, password=PASSWORD)
                approvals: list[ApprovalRequest] = []
                for index, expires_at in enumerate(
                    (now - timedelta(minutes=1), now + timedelta(minutes=10))
                ):
                    conversation = Conversation(owner_id=owner.id, title=f"Approval {index}")
                    session.add(conversation)
                    await session.flush()
                    run = AgentRun(
                        conversation_id=conversation.id,
                        actor_id=owner.id,
                        kind=RunKind.CHAT,
                        client_request_id=f"approval-maintenance-{index}",
                        input_hash=str(index) * 64,
                        status=RunStatus.WAITING_APPROVAL,
                        checkpoint_thread_id=f"run:{uuid4()}",
                        prompt_version="test",
                        model="fake",
                    )
                    session.add(run)
                    await session.flush()
                    approval = await ApprovalService().create_ticket_draft(
                        session,
                        owner_id=owner.id,
                        run_id=run.id,
                        action_id=f"maintenance-action-{index}",
                        arguments=CreateTicketArguments(
                            title="VPN approval maintenance",
                            description="A sufficiently long description for the approval draft.",
                            issue_type="vpn",
                            severity="normal",
                        ),
                        now=expires_at - timedelta(minutes=15),
                    )
                    approvals.append(approval)

            assert await expire_pending_approvals(database, now=now, limit=1) == 1
            assert await expire_pending_approvals(database, now=now, limit=1) == 0

            async with database.session() as session:
                expired = await session.get(ApprovalRequest, approvals[0].id)
                future = await session.get(ApprovalRequest, approvals[1].id)
                expired_run = await session.get(AgentRun, approvals[0].run_id)
                future_run = await session.get(AgentRun, approvals[1].run_id)
                event = await session.scalar(
                    select(RunEvent).where(
                        RunEvent.run_id == approvals[0].run_id,
                        RunEvent.dedupe_key == f"approval-expired:{approvals[0].id}",
                    )
                )
                assert expired is not None and expired.status == ApprovalStatus.EXPIRED.value
                assert future is not None and future.status == ApprovalStatus.PENDING.value
                assert expired_run is not None and expired_run.status == RunStatus.CANCELLED
                assert expired_run.outcome == "approval_expired"
                assert future_run is not None and future_run.status == RunStatus.WAITING_APPROVAL
                assert event is not None and event.type == "run.cancelled"
        finally:
            await database.close()

    asyncio.run(scenario())
