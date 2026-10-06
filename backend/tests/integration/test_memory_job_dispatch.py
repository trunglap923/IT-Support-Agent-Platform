from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import func, select

from app.auth.passwords import hash_password
from app.db import Database
from app.db.models import (
    AgentRun,
    Department,
    MemoryCandidate,
    MemoryExtractionJob,
    Message,
    RunStatus,
    User,
    UserRole,
)
from app.jobs.memory import execute_memory_extraction, reconcile_memory_extractions
from app.jobs.worker import execute_support_run
from app.observability import NoopAIObserver
from app.providers.embeddings import FakeEmbeddingProvider
from app.providers.fake import FakeTextProvider
from app.repositories.conversations import ConversationRepository
from app.services.conversations.submission import RunSubmissionService


class RecordingRunDispatcher:
    async def ensure_available(self) -> None:
        return None

    async def enqueue_run(self, run_id: UUID) -> None:
        del run_id


class VerifyingMemoryDispatcher:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.job_ids: list[UUID] = []

    async def enqueue_memory_extraction(self, job_id: UUID) -> None:
        # If this callback can read all three rows, enqueue happened after commit.
        async with self.database.session() as session:
            job = await session.get(MemoryExtractionJob, job_id)
            assert job is not None
            run = await session.get(AgentRun, job.run_id)
            assert run is not None and run.status is RunStatus.COMPLETED
            assistant_count = await session.scalar(
                select(func.count(Message.id)).where(
                    Message.run_id == run.id,
                    Message.role == "assistant",
                )
            )
            assert assistant_count == 1
        self.job_ids.append(job_id)


def test_memory_job_is_committed_before_enqueue_and_replay_is_idempotent(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        embeddings = FakeEmbeddingProvider()
        memory_dispatcher = VerifyingMemoryDispatcher(database)
        try:
            async with database.session() as session, session.begin():
                department = Department(key="engineering", name="Engineering")
                session.add(department)
                await session.flush()
                user = User(
                    email="memory-worker@example.com",
                    display_name="Memory Worker",
                    password_hash=hash_password("test-password"),
                    role=UserRole.EMPLOYEE,
                    department_id=department.id,
                    active=True,
                    memory_enabled=True,
                    memory_epoch=1,
                )
                session.add(user)
                await session.flush()
                conversation = await ConversationRepository().create(
                    session,
                    owner_id=user.id,
                    title="Remember my device",
                )

            submitted = await RunSubmissionService(database, RecordingRunDispatcher()).submit(
                actor_id=user.id,
                conversation_id=conversation.id,
                content="Tôi dùng Ubuntu 24.04.",
                client_request_id="memory-after-final-commit",
            )
            result = await execute_support_run(
                database,
                run_id=submitted.run_id,
                provider=FakeTextProvider(),
                embedding_provider=embeddings,
                observer=NoopAIObserver(),
                model="fake",
                memory_dispatcher=memory_dispatcher,
            )
            assert result.status == "processed"
            assert len(memory_dispatcher.job_ids) == 1
            job_id = memory_dispatcher.job_ids[0]

            assert await execute_memory_extraction(database, job_id=job_id) == "completed"
            assert await execute_memory_extraction(database, job_id=job_id) == "completed"
            async with database.session() as session:
                candidate_count = await session.scalar(
                    select(func.count(MemoryCandidate.id)).where(MemoryCandidate.job_id == job_id)
                )
            assert candidate_count == 1

            # Completed jobs are not redelivered by reconciliation.
            assert await reconcile_memory_extractions(database, memory_dispatcher) == 0
        finally:
            await embeddings.close()
            await database.close()

    asyncio.run(scenario())
