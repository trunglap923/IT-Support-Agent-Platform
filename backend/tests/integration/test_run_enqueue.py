import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import func, select, update

from app.auth.passwords import hash_password
from app.db import Database
from app.db.models import AgentRun, Department, Message, RunEvent, User, UserRole
from app.jobs.dispatch import BrokerUnavailableError
from app.jobs.reconcile import reconcile_queued_run_dispatches
from app.jobs.worker import execute_fake_run
from app.repositories.conversations import ConversationRepository
from app.services.conversations.submission import RunSubmissionService


class RecordingDispatcher:
    def __init__(self, *, fail_preflight: bool = False, fail_enqueue: bool = False) -> None:
        self.fail_preflight = fail_preflight
        self.fail_enqueue = fail_enqueue
        self.enqueued: list[UUID] = []

    async def ensure_available(self) -> None:
        if self.fail_preflight:
            raise BrokerUnavailableError("unavailable before commit")

    async def enqueue_run(self, run_id: UUID) -> None:
        if self.fail_enqueue:
            raise BrokerUnavailableError("unavailable after commit")
        self.enqueued.append(run_id)


class BarrierDispatcher(RecordingDispatcher):
    def __init__(self, parties: int) -> None:
        super().__init__()
        self.parties = parties
        self.arrivals = 0
        self.ready = asyncio.Event()

    async def ensure_available(self) -> None:
        self.arrivals += 1
        if self.arrivals == self.parties:
            self.ready.set()
        await asyncio.wait_for(self.ready.wait(), timeout=5)


def test_commit_then_enqueue_failure_replay_and_worker_claim(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                department = Department(key="engineering", name="Engineering")
                session.add(department)
                await session.flush()
                user = User(
                    email="enqueue-owner@example.com",
                    display_name="Enqueue Owner",
                    password_hash=hash_password("correct-horse-battery-staple"),
                    role=UserRole.EMPLOYEE,
                    department_id=department.id,
                    active=True,
                    memory_enabled=False,
                    memory_epoch=0,
                )
                session.add(user)
                await session.flush()
                conversations = ConversationRepository()
                before_failure = await conversations.create(
                    session, owner_id=user.id, title="Preflight failure"
                )
                after_failure = await conversations.create(
                    session, owner_id=user.id, title="Post-commit failure"
                )
                race_conversation = await conversations.create(
                    session, owner_id=user.id, title="Concurrent replay"
                )
                actor_id = user.id
                before_id = before_failure.id
                after_id = after_failure.id
                race_id = race_conversation.id

            preflight_dispatcher = RecordingDispatcher(fail_preflight=True)
            with pytest.raises(BrokerUnavailableError):
                await RunSubmissionService(database, preflight_dispatcher).submit(
                    actor_id=actor_id,
                    conversation_id=before_id,
                    content="Check VPN",
                    client_request_id="preflight-request",
                )
            async with database.session() as session:
                assert await session.scalar(select(func.count()).select_from(AgentRun)) == 0

            failed_dispatcher = RecordingDispatcher(fail_enqueue=True)
            committed = await RunSubmissionService(database, failed_dispatcher).submit(
                actor_id=actor_id,
                conversation_id=after_id,
                content="Check registry",
                client_request_id="post-commit-request",
            )
            assert committed.created is True
            assert committed.enqueued is False
            assert committed.enqueue_error == "broker_unavailable"

            async with database.session() as session, session.begin():
                await session.execute(
                    update(AgentRun)
                    .where(AgentRun.id == committed.run_id)
                    .values(created_at=datetime.now(UTC) - timedelta(minutes=1))
                )
            recovery_dispatcher = RecordingDispatcher()
            assert (
                await reconcile_queued_run_dispatches(database, recovery_dispatcher, limit=10) == 1
            )
            assert recovery_dispatcher.enqueued == [committed.run_id]

            race_dispatcher = BarrierDispatcher(parties=2)
            race_service = RunSubmissionService(database, race_dispatcher)
            first, second = await asyncio.gather(
                race_service.submit(
                    actor_id=actor_id,
                    conversation_id=race_id,
                    content="Docker cannot pull",
                    client_request_id="same-request",
                ),
                race_service.submit(
                    actor_id=actor_id,
                    conversation_id=race_id,
                    content="Docker cannot pull",
                    client_request_id="same-request",
                ),
            )
            assert sum(result.created for result in (first, second)) == 1
            assert first.run_id == second.run_id
            assert race_dispatcher.enqueued == [first.run_id]

            worker_results = await asyncio.gather(
                execute_fake_run(database, run_id=first.run_id),
                execute_fake_run(database, run_id=first.run_id),
            )
            assert {result.status for result in worker_results} == {"processed", "duplicate"}

            async with database.session() as session:
                message_count = await session.scalar(
                    select(func.count())
                    .select_from(Message)
                    .where(Message.conversation_id == race_id)
                )
                events = list(
                    (
                        await session.scalars(
                            select(RunEvent)
                            .where(RunEvent.run_id == first.run_id)
                            .order_by(RunEvent.sequence)
                        )
                    ).all()
                )
                failed_events = list(
                    (
                        await session.scalars(
                            select(RunEvent)
                            .where(RunEvent.run_id == committed.run_id)
                            .order_by(RunEvent.sequence)
                        )
                    ).all()
                )
            assert message_count == 2
            assert [event.type for event in events] == [
                "run.queued",
                "run.running",
                "run.completed",
            ]
            assert [event.type for event in failed_events] == [
                "run.queued",
                "run.enqueue_failed",
            ]
        finally:
            await database.close()

    asyncio.run(scenario())
