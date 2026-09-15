import asyncio
from uuid import uuid4

from app.auth.passwords import hash_password
from app.db import Database
from app.db.models import AgentRun, Department, RunKind, RunStatus, User, UserRole
from app.repositories.conversations import ConversationRepository
from app.repositories.runs import RunRepository
from app.services.conversations.run_state import RunStateService


def test_transition_and_event_are_persistent_and_idempotent(
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
                    email="run-owner@example.com",
                    display_name="Run Owner",
                    password_hash=hash_password("correct-horse-battery-staple"),
                    role=UserRole.EMPLOYEE,
                    department_id=department.id,
                    active=True,
                    memory_enabled=False,
                    memory_epoch=0,
                )
                session.add(user)
                await session.flush()
                conversation = await ConversationRepository().create(
                    session,
                    owner_id=user.id,
                    title="State machine test",
                )
                run = AgentRun(
                    conversation_id=conversation.id,
                    actor_id=user.id,
                    kind=RunKind.CHAT,
                    client_request_id="state-request-1",
                    input_hash="c" * 64,
                    status=RunStatus.QUEUED,
                    checkpoint_thread_id=str(uuid4()),
                    prompt_version="v1",
                    model="fake",
                    counters={},
                )
                session.add(run)
                await session.flush()
                run_id, actor_id = run.id, user.id

            service = RunStateService()
            async with database.session() as session, session.begin():
                first = await service.transition(
                    session,
                    run_id=run_id,
                    actor_id=actor_id,
                    target=RunStatus.RUNNING,
                    operation_id="worker-claim-1",
                )
                assert first.applied is True
                assert first.event.sequence == 1

            async with database.session() as session, session.begin():
                replay = await service.transition(
                    session,
                    run_id=run_id,
                    actor_id=actor_id,
                    target=RunStatus.RUNNING,
                    operation_id="worker-claim-1",
                )
                assert replay.applied is False
                assert replay.event.sequence == 1

            async with database.session() as session, session.begin():
                completed = await service.transition(
                    session,
                    run_id=run_id,
                    actor_id=actor_id,
                    target=RunStatus.COMPLETED,
                    operation_id="worker-complete-1",
                    outcome="answered",
                )
                assert completed.run.finished_at is not None

            async with database.session() as session:
                events = await RunRepository().list_events_owned(
                    session,
                    run_id=run_id,
                    actor_id=actor_id,
                )
                assert [event.sequence for event in events] == [1, 2]
                assert [event.type for event in events] == ["run.running", "run.completed"]
        finally:
            await database.close()

    asyncio.run(scenario())
