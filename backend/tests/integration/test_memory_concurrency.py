from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import func, select

from app.auth.demo_identity import ensure_demo_identity
from app.db import Database
from app.db.models import Conversation, MemoryCandidate, MemoryExtractionJob, Message
from app.memory.lifecycle import MemoryConflictError, MemoryLifecycleService
from app.memory.retrieval import MemoryContextService

PASSWORD = "correct-horse-battery-staple"


def test_delete_while_extraction_runs_discards_stale_job(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        lifecycle = MemoryLifecycleService()
        owner_id: UUID
        fact_id: UUID
        running_job_id: UUID
        try:
            async with database.session() as session, session.begin():
                user = await ensure_demo_identity(session, password=PASSWORD)
                owner_id = user.id
                conversation = Conversation(owner_id=owner_id, title="Memory concurrency")
                session.add(conversation)
                await session.flush()
                confirmed_source = Message(
                    conversation_id=conversation.id,
                    role="user",
                    content="Hãy trả lời bằng tiếng Việt.",
                )
                running_source = Message(
                    conversation_id=conversation.id,
                    role="user",
                    content="Tôi dùng Ubuntu 24.04.",
                )
                session.add_all([confirmed_source, running_source])
                await session.flush()
                extraction = await lifecycle.extract_from_message(
                    session,
                    owner_id=owner_id,
                    source_message_id=confirmed_source.id,
                )
                assert extraction is not None
                fact = await lifecycle.confirm_candidate(
                    session,
                    owner_id=owner_id,
                    candidate_id=extraction.candidates[0].id,
                    expected_version=1,
                    device_id=None,
                )
                fact = await lifecycle.update_fact(
                    session,
                    owner_id=owner_id,
                    fact_id=fact.id,
                    expected_version=1,
                    value="Tiếng Việt ưu tiên",
                )
                assert fact.version == 2
                fact_id = fact.id
                running_job = await lifecycle.start_extraction_job(
                    session,
                    owner_id=owner_id,
                    source_message_id=running_source.id,
                )
                assert running_job is not None
                assert running_job.status == "pending"
                running_job_id = running_job.id

            async with database.session() as session, session.begin():
                try:
                    await lifecycle.delete_fact(
                        session,
                        owner_id=owner_id,
                        fact_id=fact_id,
                        expected_version=1,
                    )
                except MemoryConflictError:
                    pass
                else:
                    raise AssertionError("Expected stale fact version to be rejected")
                await lifecycle.delete_fact(
                    session,
                    owner_id=owner_id,
                    fact_id=fact_id,
                    expected_version=2,
                )

            async with database.session() as session, session.begin():
                result = await lifecycle.complete_extraction_job(
                    session,
                    owner_id=owner_id,
                    job_id=running_job_id,
                )
                assert result.job.status == "discarded"
                assert result.job.error_code == "stale_memory_epoch"
                assert result.candidates == ()

            async with database.session() as session:
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(MemoryCandidate)
                        .where(MemoryCandidate.job_id == running_job_id)
                    )
                    == 0
                )
                job = await session.get(MemoryExtractionJob, running_job_id)
                assert job is not None and job.status == "discarded"
                context = await MemoryContextService().context_messages(
                    session, owner_id=owner_id, device_id=None
                )
                assert context == []
        finally:
            await database.close()

    asyncio.run(scenario())
