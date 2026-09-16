from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import update

from app.auth.demo_identity import ensure_demo_identity
from app.db import Database
from app.db.models import AgentRun, Conversation, RunKind, RunStatus
from app.jobs.dispatch import BrokerUnavailableError
from app.jobs.reconcile import reconcile_queued_run_dispatches
from app.services.conversations.run_lease import RunLeaseService
from app.services.conversations.run_state import RunStateService

PASSWORD = "correct-horse-battery-staple"


class RestartingDispatcher:
    def __init__(self, *, available: bool) -> None:
        self.available = available
        self.enqueued: list[UUID] = []

    async def ensure_available(self) -> None:
        if not self.available:
            raise BrokerUnavailableError("Redis is restarting")

    async def enqueue_run(self, run_id: UUID) -> None:
        if not self.available:
            raise BrokerUnavailableError("Redis is restarting")
        self.enqueued.append(run_id)


def test_lease_reclaim_retry_limit_and_reconciliation_after_broker_restart(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        now = datetime.now(UTC)
        try:
            async with database.session() as session, session.begin():
                owner = await ensure_demo_identity(session, password=PASSWORD)
                conversations = [
                    Conversation(owner_id=owner.id, title=f"Recovery {index}") for index in range(3)
                ]
                session.add_all(conversations)
                await session.flush()
                stale = AgentRun(
                    conversation_id=conversations[0].id,
                    actor_id=owner.id,
                    kind=RunKind.CHAT,
                    client_request_id="stale-running",
                    input_hash="1" * 64,
                    status=RunStatus.QUEUED,
                    checkpoint_thread_id=f"run:{uuid4()}",
                    prompt_version="test",
                    model="fake",
                )
                resume = AgentRun(
                    conversation_id=conversations[1].id,
                    actor_id=owner.id,
                    kind=RunKind.MANUAL_TICKET,
                    client_request_id="resume-queued",
                    input_hash="2" * 64,
                    status=RunStatus.RESUME_QUEUED,
                    checkpoint_thread_id=f"run:{uuid4()}",
                    prompt_version="test",
                    model="none",
                    created_at=now - timedelta(minutes=2),
                )
                exhausted = AgentRun(
                    conversation_id=conversations[2].id,
                    actor_id=owner.id,
                    kind=RunKind.CHAT,
                    client_request_id="attempts-exhausted",
                    input_hash="3" * 64,
                    status=RunStatus.RUNNING,
                    checkpoint_thread_id=f"run:{uuid4()}",
                    prompt_version="test",
                    model="fake",
                    attempts=3,
                    lease_owner="dead-worker",
                    lease_until=now - timedelta(seconds=5),
                )
                session.add_all([stale, resume, exhausted])
                await session.flush()
                stale_id, resume_id, exhausted_id = stale.id, resume.id, exhausted.id
                actor_id = owner.id

            lease = RunLeaseService()
            state = RunStateService()
            async with database.session() as session, session.begin():
                first = await lease.claim(
                    session,
                    run_id=stale_id,
                    worker_id="worker-a",
                    lease_seconds=30,
                    max_attempts=3,
                    now=now,
                )
                assert first.outcome == "claimed"
                await state.transition(
                    session,
                    run_id=stale_id,
                    actor_id=actor_id,
                    target=RunStatus.RUNNING,
                    operation_id="initial-worker-claim",
                    now=now,
                )
            async with database.session() as session, session.begin():
                busy = await lease.claim(
                    session,
                    run_id=stale_id,
                    worker_id="worker-b",
                    lease_seconds=30,
                    max_attempts=3,
                    now=now + timedelta(seconds=1),
                )
                assert busy.outcome == "busy"
                await session.execute(
                    update(AgentRun)
                    .where(AgentRun.id == stale_id)
                    .values(lease_until=now - timedelta(seconds=1))
                )

            unavailable = RestartingDispatcher(available=False)
            assert (
                await reconcile_queued_run_dispatches(
                    database,
                    unavailable,
                    older_than_seconds=30,
                    max_attempts=3,
                )
                == 0
            )
            recovered_dispatcher = RestartingDispatcher(available=True)
            assert (
                await reconcile_queued_run_dispatches(
                    database,
                    recovered_dispatcher,
                    older_than_seconds=30,
                    max_attempts=3,
                )
                == 2
            )
            assert set(recovered_dispatcher.enqueued) == {stale_id, resume_id}

            async with database.session() as session, session.begin():
                reclaimed = await lease.claim(
                    session,
                    run_id=stale_id,
                    worker_id="worker-b",
                    lease_seconds=30,
                    max_attempts=3,
                    now=now + timedelta(seconds=2),
                )
                assert reclaimed.outcome == "reclaimed"
                assert reclaimed.run is not None and reclaimed.run.attempts == 2
                assert not await lease.heartbeat(
                    session,
                    run_id=stale_id,
                    worker_id="worker-a",
                    lease_seconds=30,
                    now=now,
                )
                assert await lease.heartbeat(
                    session,
                    run_id=stale_id,
                    worker_id="worker-b",
                    lease_seconds=30,
                    now=now,
                )

            async with database.session() as session, session.begin():
                stopped = await lease.claim(
                    session,
                    run_id=exhausted_id,
                    worker_id="worker-c",
                    lease_seconds=30,
                    max_attempts=3,
                    now=now,
                )
                assert stopped.outcome == "exhausted"
                assert stopped.run is not None
                assert stopped.run.status is RunStatus.FAILED
                assert stopped.run.error_code == "recovery_attempts_exhausted"
        finally:
            await database.close()

    asyncio.run(scenario())
