from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import func, select

from app.agent.working_memory.service import WorkingMemoryService
from app.auth.demo_identity import ensure_demo_identity
from app.db import Database
from app.db.models import (
    AgentRun,
    Conversation,
    RunKind,
    RunStatus,
    WorkingMemoryEvent,
    WorkingMemorySnapshotRecord,
)

PASSWORD = "correct-horse-battery-staple"


def test_initial_snapshot_is_persisted_before_its_event(migrated_database_url: str) -> None:
    """Creating the first event in one transaction must satisfy the snapshot foreign key."""

    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                owner = await ensure_demo_identity(session, password=PASSWORD)
                conversation = Conversation(owner_id=owner.id, title="Working memory regression")
                session.add(conversation)
                await session.flush()
                run = AgentRun(
                    conversation_id=conversation.id,
                    actor_id=owner.id,
                    kind=RunKind.CHAT,
                    client_request_id="working-memory-parent-before-event",
                    input_hash="a" * 64,
                    status=RunStatus.RUNNING,
                    checkpoint_thread_id=f"run:{uuid4()}",
                    prompt_version="test",
                    model="fake",
                )
                session.add(run)
                await session.flush()

                snapshot = await WorkingMemoryService().create_or_load(
                    session,
                    run_id=run.id,
                    conversation_id=conversation.id,
                    owner_id=owner.id,
                    current_message_id=uuid4(),
                    query="Xin chào",
                    device_id=None,
                )
                run_id = run.id
                memory_id = snapshot.working_memory_id

            async with database.session() as session:
                stored_snapshot = await session.get(WorkingMemorySnapshotRecord, memory_id)
                event_count = await session.scalar(
                    select(func.count())
                    .select_from(WorkingMemoryEvent)
                    .where(WorkingMemoryEvent.working_memory_id == memory_id)
                )
                first_event = await session.scalar(
                    select(WorkingMemoryEvent).where(
                        WorkingMemoryEvent.working_memory_id == memory_id,
                        WorkingMemoryEvent.sequence == 1,
                    )
                )

                assert stored_snapshot is not None
                assert stored_snapshot.run_id == run_id
                assert event_count == 1
                assert first_event is not None
                assert first_event.event_type == "created"
                assert first_event.snapshot_version == 1
        finally:
            await database.close()

    asyncio.run(scenario())
