from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.auth.demo_identity import ensure_demo_accounts, ensure_demo_identity
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
    User,
    UserDevice,
)
from app.demo_seed import ensure_demo_devices_and_service_states
from app.services.approvals import ApprovalService, canonical_argument_hash
from app.services.tickets import (
    TicketCreationReceipt,
    TicketWriteRejectedError,
    TicketWriteService,
)
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


def test_ticket_execution_rechecks_device_ownership(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_accounts(session, password=PASSWORD)
                await ensure_demo_devices_and_service_states(session)
                owner = await session.scalar(
                    select(User).where(User.email == "employee.engineering@example.com")
                )
                other_owner = await session.scalar(
                    select(User).where(User.email == "employee.operations@example.com")
                )
                assert owner is not None and other_owner is not None
                wrong_device_id = await session.scalar(
                    select(UserDevice.id).where(UserDevice.owner_id == other_owner.id)
                )
                assert wrong_device_id is not None

                conversation = Conversation(owner_id=owner.id, title="Tampered device")
                session.add(conversation)
                await session.flush()
                run = AgentRun(
                    conversation_id=conversation.id,
                    actor_id=owner.id,
                    kind=RunKind.CHAT,
                    client_request_id="tampered-device-write",
                    input_hash="a" * 64,
                    status=RunStatus.WAITING_APPROVAL,
                    checkpoint_thread_id=f"run:{uuid4()}",
                    prompt_version="test",
                    model="fake",
                )
                session.add(run)
                await session.flush()
                arguments = CreateTicketArguments(
                    title="Tampered approval device",
                    description="The stored approval references another user's device.",
                    issue_type="other",
                    severity="normal",
                    device_id=wrong_device_id,
                )
                canonical, digest = canonical_argument_hash(arguments.model_dump(mode="json"))
                now = datetime.now(UTC)
                approval = ApprovalRequest(
                    action_id="tampered-device-action",
                    run_id=run.id,
                    owner_id=owner.id,
                    tool_name="create_ticket",
                    canonical_args=canonical,
                    arguments_hash=digest,
                    status=ApprovalStatus.APPROVED.value,
                    expires_at=now + timedelta(minutes=15),
                    decided_by=owner.id,
                    decided_at=now,
                    version=2,
                )
                session.add(approval)
                await session.flush()

                try:
                    await TicketWriteService().create_from_approval(
                        session,
                        approval_id=approval.id,
                        owner_id=owner.id,
                    )
                except TicketWriteRejectedError as error:
                    assert str(error) == "Ticket device is unavailable for its owner"
                else:
                    raise AssertionError("Wrong-owner device was accepted during ticket execution")
                assert await session.scalar(select(func.count()).select_from(Ticket)) == 0
        finally:
            await database.close()

    asyncio.run(scenario())
