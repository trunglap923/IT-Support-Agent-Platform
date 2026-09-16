from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.auth.demo_identity import ensure_demo_identity
from app.db import Database
from app.db.models import (
    AgentRun,
    ApprovalRequest,
    ApprovalStatus,
    Conversation,
    RunKind,
    RunStatus,
    Ticket,
    TicketEvent,
)
from app.services.approvals import ApprovalService
from app.services.tickets import TicketCreationReceipt, TicketWriteService
from app.tools.schemas import CreateTicketArguments

PASSWORD = "correct-horse-battery-staple"


def test_ticket_creation_is_idempotent_under_duplicate_execution(
    migrated_database_url: str,
) -> None:
    async def seed() -> tuple[UUID, UUID]:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                owner = await ensure_demo_identity(session, password=PASSWORD)
                conversation = Conversation(owner_id=owner.id, title="Ticket write")
                session.add(conversation)
                await session.flush()
                run = AgentRun(
                    conversation_id=conversation.id,
                    actor_id=owner.id,
                    kind=RunKind.CHAT,
                    client_request_id="ticket-write",
                    input_hash="f" * 64,
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
                    action_id="ticket-write-action",
                    arguments=CreateTicketArguments(
                        title="VPN access is unavailable",
                        description="VPN is still unavailable after documented troubleshooting.",
                        issue_type="vpn",
                        severity="high",
                    ),
                )
                approval.status = ApprovalStatus.APPROVED.value
                approval.decided_by = owner.id
                approval.decided_at = datetime.now(UTC)
                approval.version += 1
                return owner.id, approval.id
        finally:
            await database.close()

    async def execute(owner_id: UUID, approval_id: UUID) -> TicketCreationReceipt:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                return await TicketWriteService().create_from_approval(
                    session,
                    approval_id=approval_id,
                    owner_id=owner_id,
                )
        finally:
            await database.close()

    async def scenario() -> None:
        owner_id, approval_id = await seed()
        first, duplicate = await asyncio.gather(
            execute(owner_id, approval_id),
            execute(owner_id, approval_id),
        )
        assert first.ticket_id == duplicate.ticket_id
        assert {first.applied, duplicate.applied} == {True, False}

        database = Database(migrated_database_url)
        try:
            async with database.session() as session:
                ticket_count = await session.scalar(
                    select(func.count())
                    .select_from(Ticket)
                    .where(Ticket.approval_id == approval_id)
                )
                event_count = await session.scalar(select(func.count()).select_from(TicketEvent))
                approval = await session.get(ApprovalRequest, approval_id)
                assert ticket_count == 1
                assert event_count == 1
                assert approval is not None
                assert approval.status == ApprovalStatus.EXECUTED.value
                assert approval.executed_at is not None
        finally:
            await database.close()

    asyncio.run(scenario())
