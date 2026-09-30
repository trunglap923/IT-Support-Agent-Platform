from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import func, select

from app.auth.demo_identity import ensure_demo_identity
from app.db import Database
from app.db.models import (
    Conversation,
    MemoryCandidate,
    MemoryFact,
    Message,
)
from app.memory.lifecycle import MemoryLifecycleService

PASSWORD = "correct-horse-battery-staple"


def test_always_on_memory_only_creates_pending_candidates(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        service = MemoryLifecycleService()
        try:
            async with database.session() as session, session.begin():
                user = await ensure_demo_identity(session, password=PASSWORD)
                conversation = Conversation(owner_id=user.id, title="Thiết lập thiết bị")
                session.add(conversation)
                await session.flush()
                message = Message(
                    conversation_id=conversation.id,
                    role="user",
                    content="Tôi dùng Windows 11 và hãy trả lời bằng tiếng Việt.",
                )
                session.add(message)
                await session.flush()
                result = await service.extract_from_message(
                    session, owner_id=user.id, source_message_id=message.id
                )
                assert result is not None
                assert result.created is True
                assert {candidate.key for candidate in result.candidates} == {
                    "operating_system",
                    "preferred_language",
                }
                assert all(candidate.status == "pending" for candidate in result.candidates)
                repeated = await service.extract_from_message(
                    session, owner_id=user.id, source_message_id=message.id
                )
                assert repeated is not None
                assert repeated.created is False
                assert repeated.job.id == result.job.id

            async with database.session() as session:
                assert await session.scalar(select(func.count()).select_from(MemoryFact)) == 0
                assert await session.scalar(select(func.count()).select_from(MemoryCandidate)) == 2
        finally:
            await database.close()

    asyncio.run(scenario())


def test_candidate_source_must_belong_to_owner(migrated_database_url: str) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        service = MemoryLifecycleService()
        try:
            async with database.session() as session, session.begin():
                owner = await ensure_demo_identity(session, password=PASSWORD)
                conversation = Conversation(owner_id=owner.id, title="Private")
                session.add(conversation)
                await session.flush()
                message = Message(
                    conversation_id=conversation.id,
                    role="user",
                    content="Tôi dùng Ubuntu 24.04.",
                )
                session.add(message)
                await session.flush()
                other_owner = uuid4()

                # A nonexistent actor cannot use another user's source message.
                try:
                    await service.extract_from_message(
                        session, owner_id=other_owner, source_message_id=message.id
                    )
                except LookupError:
                    pass
                else:
                    raise AssertionError("Expected owner lookup to fail")
        finally:
            await database.close()

    asyncio.run(scenario())
