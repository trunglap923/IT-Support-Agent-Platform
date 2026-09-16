from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from app.auth.passwords import hash_password
from app.db import Database
from app.db.models import (
    Department,
    Document,
    DocumentChunk,
    DocumentVersion,
    DocumentVersionStatus,
    DocumentVisibility,
    Message,
    User,
    UserRole,
)
from app.jobs.worker import execute_support_run
from app.observability import NoopAIObserver
from app.providers.embeddings import FakeEmbeddingProvider
from app.providers.fake import FakeTextProvider
from app.repositories.conversations import ConversationRepository
from app.services.conversations.submission import RunSubmissionService


class RecordingDispatcher:
    async def ensure_available(self) -> None:
        return None

    async def enqueue_run(self, run_id: UUID) -> None:
        del run_id


def test_fake_rag_chat_citation_and_no_answer_end_to_end(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        embeddings = FakeEmbeddingProvider()
        try:
            async with database.session() as session, session.begin():
                department = Department(key="engineering", name="Engineering")
                session.add(department)
                await session.flush()
                user = User(
                    email="rag-demo@example.com",
                    display_name="RAG Demo",
                    password_hash=hash_password("test-password"),
                    role=UserRole.EMPLOYEE,
                    department_id=department.id,
                    active=True,
                    memory_enabled=False,
                    memory_epoch=0,
                )
                session.add(user)
                await session.flush()
                document = Document(
                    document_key="vpn-ubuntu",
                    title="VPN on Ubuntu",
                    visibility=DocumentVisibility.COMPANY,
                    department_id=None,
                )
                session.add(document)
                await session.flush()
                version = DocumentVersion(
                    document_id=document.id,
                    version_label="v1",
                    status=DocumentVersionStatus.PUBLISHED,
                    authority="internal-it",
                    language="en",
                    media_type="text/markdown",
                    source_checksum="a" * 64,
                    storage_key="vpn-ubuntu.md",
                    effective_at=datetime(2026, 1, 1, tzinfo=UTC),
                    embedding_model="fake-embedding-v2",
                    embedding_dimensions=1536,
                )
                session.add(version)
                await session.flush()
                document.current_version_id = version.id
                content = "VPN Ubuntu connect client sign in using company SSO"
                vector = (await embeddings.embed([content], operation_id="seed")).vectors[0]
                session.add(
                    DocumentChunk(
                        id=uuid4(),
                        version_id=version.id,
                        ordinal=0,
                        page_number=1,
                        section="Connect",
                        source_path="vpn-ubuntu.md",
                        source_token_start=0,
                        source_token_end=len(content.split()),
                        content=content,
                        token_count=len(content.split()),
                        content_hash=hashlib.sha256(content.encode()).hexdigest(),
                        embedding_model="fake-embedding-v2",
                        embedding_dimensions=1536,
                        embedding=list(vector),
                    )
                )
                answered_conversation = await ConversationRepository().create(
                    session, owner_id=user.id, title="VPN"
                )
                unknown_conversation = await ConversationRepository().create(
                    session, owner_id=user.id, title="Unknown"
                )
                actor_id = user.id

            service = RunSubmissionService(database, RecordingDispatcher())
            answered = await service.submit(
                actor_id=actor_id,
                conversation_id=answered_conversation.id,
                content="VPN Ubuntu connect SSO",
                client_request_id="rag-e2e-answer",
            )
            await execute_support_run(
                database,
                run_id=answered.run_id,
                provider=FakeTextProvider(),
                embedding_provider=embeddings,
                observer=NoopAIObserver(),
                model="fake",
            )
            unknown = await service.submit(
                actor_id=actor_id,
                conversation_id=unknown_conversation.id,
                content="Quantum printer teleportation",
                client_request_id="rag-e2e-no-answer",
            )
            await execute_support_run(
                database,
                run_id=unknown.run_id,
                provider=FakeTextProvider(),
                embedding_provider=embeddings,
                observer=NoopAIObserver(),
                model="fake",
            )

            async with database.session() as session:
                messages = list(
                    (
                        await session.scalars(
                            select(Message)
                            .where(Message.role == "assistant")
                            .order_by(Message.created_at)
                        )
                    ).all()
                )
            assert messages[0].outcome == "answered"
            assert len(messages[0].citations) == 1
            assert messages[0].citations[0]["title"] == "VPN on Ubuntu"
            assert messages[1].outcome == "no_answer"
            assert messages[1].citations == []
        finally:
            await embeddings.close()
            await database.close()

    asyncio.run(scenario())
