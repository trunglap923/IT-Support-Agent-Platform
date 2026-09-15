import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.passwords import hash_password
from app.db import Database
from app.db.models import (
    AgentRun,
    Department,
    RunEvent,
    RunKind,
    RunStatus,
    User,
    UserRole,
)
from app.repositories.conversations import ConversationRepository
from app.repositories.runs import RunRepository


def employee(email: str, department_id) -> User:  # type: ignore[no-untyped-def]
    return User(
        email=email,
        display_name=email.split("@", maxsplit=1)[0],
        password_hash=hash_password("correct-horse-battery-staple"),
        role=UserRole.EMPLOYEE,
        department_id=department_id,
        active=True,
        memory_enabled=False,
        memory_epoch=0,
    )


def test_conversation_run_and_events_are_owner_scoped(migrated_database_url: str) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                department = Department(key="engineering", name="Engineering")
                session.add(department)
                await session.flush()
                alice = employee("alice@example.com", department.id)
                bob = employee("bob@example.com", department.id)
                session.add_all([alice, bob])
                await session.flush()
                conversation = await ConversationRepository().create(
                    session, owner_id=alice.id, title="Private incident"
                )
                run = AgentRun(
                    conversation_id=conversation.id,
                    actor_id=alice.id,
                    kind=RunKind.CHAT,
                    client_request_id="request-1",
                    input_hash="a" * 64,
                    status=RunStatus.QUEUED,
                    checkpoint_thread_id=str(uuid4()),
                    prompt_version="v1",
                    model="fake",
                    counters={},
                )
                session.add(run)
                await session.flush()
                event = RunEvent(
                    run_id=run.id,
                    sequence=1,
                    type="queued",
                    dedupe_key="queued-initial",
                    safe_payload={},
                )
                session.add(event)
                alice_id, bob_id = alice.id, bob.id
                conversation_id, run_id = conversation.id, run.id

            async with database.session() as session:
                conversations = ConversationRepository()
                runs = RunRepository()
                assert (
                    await conversations.get_owned(
                        session, conversation_id=conversation_id, owner_id=alice_id
                    )
                    is not None
                )
                assert (
                    await conversations.get_owned(
                        session, conversation_id=conversation_id, owner_id=bob_id
                    )
                    is None
                )
                assert await runs.get_owned(session, run_id=run_id, actor_id=bob_id) is None
                assert await runs.list_events_owned(session, run_id=run_id, actor_id=bob_id) == []
                assert (
                    len(await runs.list_events_owned(session, run_id=run_id, actor_id=alice_id))
                    == 1
                )
        finally:
            await database.close()

    asyncio.run(scenario())


def test_database_rejects_run_for_wrong_conversation_owner(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session:
                department = Department(key="engineering", name="Engineering")
                session.add(department)
                await session.flush()
                alice = employee("alice@example.com", department.id)
                bob = employee("bob@example.com", department.id)
                session.add_all([alice, bob])
                await session.flush()
                conversation = await ConversationRepository().create(
                    session, owner_id=alice.id, title="Alice only"
                )
                session.add(
                    AgentRun(
                        conversation_id=conversation.id,
                        actor_id=bob.id,
                        kind=RunKind.CHAT,
                        client_request_id="request-wrong-owner",
                        input_hash="b" * 64,
                        status=RunStatus.QUEUED,
                        checkpoint_thread_id=str(uuid4()),
                        prompt_version="v1",
                        model="fake",
                        counters={},
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.flush()
                await session.rollback()
        finally:
            await database.close()

    asyncio.run(scenario())
