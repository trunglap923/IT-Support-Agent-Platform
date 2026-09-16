from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, update

from app.agent.approval_checkpoint import pause_ticket_approval
from app.auth.demo_identity import ensure_demo_identity
from app.db import Database
from app.db.models import (
    AgentRun,
    ApprovalRequest,
    ApprovalStatus,
    Conversation,
    Message,
    RunKind,
    RunStatus,
    Ticket,
)
from app.jobs.worker import execute_fake_run
from app.services.approvals import ApprovalService
from app.services.conversations.run_lease import RunLeaseService
from app.services.conversations.run_state import RunStateService
from app.services.tickets import TicketWriteService
from app.tools import ToolExecutionContext, ToolExecutor
from app.tools.schemas import CreateTicketArguments

PASSWORD = "correct-horse-battery-staple"


def test_tool_timeout_is_unknown_and_retryable() -> None:
    async def slow_search(_query: str, _limit: int) -> dict[str, object]:
        await asyncio.sleep(0.05)
        return {"results": []}

    async def scenario() -> None:
        executor = ToolExecutor(
            context=ToolExecutionContext(
                actor_id=uuid4(),
                run_id=uuid4(),
                database_url="postgresql+asyncpg://unused:unused@127.0.0.1/unused",
            ),
            local_search=slow_search,
            timeout_seconds=0.001,
        )
        result = await executor.execute(
            call_id="timeout-call",
            name="search_knowledge_base",
            arguments={"query": "vpn timeout", "limit": 3},
        )
        assert result.status == "unknown"
        assert result.error is not None
        assert result.error.code == "timeout"
        assert result.error.retryable is True

    asyncio.run(scenario())


def test_worker_crash_reclaim_and_committed_ticket_receipt_recovery(
    migrated_database_url: str,
) -> None:
    async def seed_crashed_worker() -> UUID:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                owner = await ensure_demo_identity(session, password=PASSWORD)
                conversation = Conversation(owner_id=owner.id, title="Worker crash")
                session.add(conversation)
                await session.flush()
                run = AgentRun(
                    conversation_id=conversation.id,
                    actor_id=owner.id,
                    kind=RunKind.CHAT,
                    client_request_id="worker-crash-recovery",
                    input_hash="7" * 64,
                    status=RunStatus.QUEUED,
                    checkpoint_thread_id=f"run:{uuid4()}",
                    prompt_version="test",
                    model="fake",
                )
                session.add(run)
                await session.flush()
                session.add(
                    Message(
                        conversation_id=conversation.id,
                        run_id=run.id,
                        role="user",
                        content="How can I restore VPN access?",
                        citations=[],
                    )
                )
                run_id = run.id
                actor_id = owner.id
            async with database.session() as session, session.begin():
                claim = await RunLeaseService().claim(
                    session,
                    run_id=run_id,
                    worker_id="crashed-worker",
                    lease_seconds=30,
                    max_attempts=3,
                )
                assert claim.acquired
                await RunStateService().transition(
                    session,
                    run_id=run_id,
                    actor_id=actor_id,
                    target=RunStatus.RUNNING,
                    operation_id="crashed-worker-claim",
                )
                await session.execute(
                    update(AgentRun)
                    .where(AgentRun.id == run_id)
                    .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
                )
            return run_id
        finally:
            await database.close()

    async def recover_worker(run_id: UUID) -> None:
        database = Database(migrated_database_url)
        try:
            result = await execute_fake_run(database, run_id=run_id)
            assert result.status == "processed"
            async with database.session() as session:
                run = await session.get(AgentRun, run_id)
                assistant_count = await session.scalar(
                    select(func.count())
                    .select_from(Message)
                    .where(Message.run_id == run_id, Message.role == "assistant")
                )
                assert run is not None
                assert run.status is RunStatus.COMPLETED
                assert run.attempts == 2
                assert run.lease_owner is None and run.lease_until is None
                assert assistant_count == 1
        finally:
            await database.close()

    crashed_run_id = asyncio.run(seed_crashed_worker())
    asyncio.run(recover_worker(crashed_run_id))

    async def seed_approval() -> tuple[UUID, UUID, str, UUID, str]:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                owner = await ensure_demo_identity(session, password=PASSWORD)
                conversation = Conversation(owner_id=owner.id, title="Receipt recovery")
                session.add(conversation)
                await session.flush()
                thread_id = f"approval:{uuid4()}"
                run = AgentRun(
                    conversation_id=conversation.id,
                    actor_id=owner.id,
                    kind=RunKind.MANUAL_TICKET,
                    client_request_id="receipt-recovery",
                    input_hash="8" * 64,
                    status=RunStatus.WAITING_APPROVAL,
                    checkpoint_thread_id=thread_id,
                    prompt_version="test",
                    model="none",
                )
                session.add(run)
                await session.flush()
                approval = await ApprovalService().create_ticket_draft(
                    session,
                    owner_id=owner.id,
                    run_id=run.id,
                    action_id="receipt-recovery-action",
                    arguments=CreateTicketArguments(
                        title="Create recovery ticket",
                        description="Create one ticket despite a crash after commit.",
                        issue_type="other",
                        severity="normal",
                    ),
                )
                return owner.id, run.id, thread_id, approval.id, approval.arguments_hash
        finally:
            await database.close()

    owner_id, run_id, thread_id, approval_id, arguments_hash = asyncio.run(seed_approval())
    pause_ticket_approval(
        database_url=migrated_database_url,
        checkpoint_thread_id=thread_id,
        run_id=run_id,
        actor_id=owner_id,
        approval_id=approval_id,
        arguments_hash=arguments_hash,
    )

    async def commit_receipt_then_recover() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                approval = await session.get(ApprovalRequest, approval_id)
                assert approval is not None
                approval.status = ApprovalStatus.APPROVED.value
                approval.decided_by = owner_id
                approval.decided_at = datetime.now(UTC)
                approval.version += 1
                run = await session.get(AgentRun, run_id)
                assert run is not None
                run.status = RunStatus.RUNNING
                run.lease_owner = "crashed-approval-worker"
                run.lease_until = datetime.now(UTC) - timedelta(seconds=1)
                run.attempts = 1
                run.version += 1
            # Simulate a worker that commits the external-effect receipt, then crashes
            # before it can mark the run complete.
            async with database.session() as session, session.begin():
                receipt = await TicketWriteService().create_from_approval(
                    session,
                    approval_id=approval_id,
                    owner_id=owner_id,
                )
                assert receipt.applied is True

            recovered = await execute_fake_run(database, run_id=run_id)
            assert recovered.status == "resumed"
            duplicate = await execute_fake_run(database, run_id=run_id)
            assert duplicate.status == "duplicate"
            async with database.session() as session:
                ticket_count = await session.scalar(
                    select(func.count())
                    .select_from(Ticket)
                    .where(Ticket.approval_id == approval_id)
                )
                approval = await session.get(ApprovalRequest, approval_id)
                run = await session.get(AgentRun, run_id)
                assert ticket_count == 1
                assert approval is not None and approval.status == ApprovalStatus.EXECUTED.value
                assert run is not None and run.status is RunStatus.COMPLETED
                assert run.outcome == "ticket_created"
        finally:
            await database.close()

    asyncio.run(commit_receipt_then_recover())
