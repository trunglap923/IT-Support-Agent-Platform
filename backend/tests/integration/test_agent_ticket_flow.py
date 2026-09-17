from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.demo_identity import ensure_demo_identity
from app.config import Settings
from app.db import Database
from app.db.models import AgentRun, ApprovalRequest, Conversation, Message, RunStatus, Ticket
from app.jobs.worker import execute_support_run
from app.main import create_app
from app.observability import NoopAIObserver
from app.providers.embeddings import FakeEmbeddingProvider
from app.providers.fake import FakeTextProvider
from app.services.conversations.submission import RunSubmissionService

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


class RecordingDispatcher:
    def __init__(self) -> None:
        self.enqueued: list[UUID] = []

    async def ensure_available(self) -> None:
        return None

    async def enqueue_run(self, run_id: UUID) -> None:
        self.enqueued.append(run_id)


def test_chat_ticket_proposal_requires_approval_before_write(
    migrated_database_url: str,
) -> None:
    async def propose() -> tuple[UUID, UUID]:
        database = Database(migrated_database_url)
        embeddings = FakeEmbeddingProvider()
        try:
            async with database.session() as session, session.begin():
                owner = await ensure_demo_identity(session, password=PASSWORD)
                conversation = Conversation(owner_id=owner.id, title="Agent ticket")
                session.add(conversation)
                await session.flush()
            submitted = await RunSubmissionService(database, RecordingDispatcher()).submit(
                actor_id=owner.id,
                conversation_id=conversation.id,
                content="Tạo ticket giúp tôi vì VPN không kết nối được.",
                client_request_id="agent-ticket-proposal",
            )
            result = await execute_support_run(
                database,
                run_id=submitted.run_id,
                provider=FakeTextProvider(),
                embedding_provider=embeddings,
                observer=NoopAIObserver(),
                model="fake",
            )
            assert result.status == "waiting_approval"
            async with database.session() as session:
                run = await session.get(AgentRun, submitted.run_id)
                approval = await session.scalar(
                    select(ApprovalRequest).where(ApprovalRequest.run_id == submitted.run_id)
                )
                ticket_count = len((await session.scalars(select(Ticket.id))).all())
                assert run is not None and run.status is RunStatus.WAITING_APPROVAL
                assert approval is not None and approval.status == "pending"
                assert ticket_count == 0
                return submitted.run_id, approval.id
        finally:
            await embeddings.close()
            await database.close()

    run_id, approval_id = asyncio.run(propose())
    dispatcher = RecordingDispatcher()
    settings = Settings(
        database_url=migrated_database_url,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )
    with TestClient(
        create_app(settings=settings, run_dispatcher=dispatcher),
        base_url=ORIGIN,
    ) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        approved = client.post(
            f"/api/v1/approvals/{approval_id}/decision",
            json={"decision": "approve", "expected_version": 1},
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": login.json()["csrf_token"],
            },
        )
        assert approved.status_code == 200
        assert dispatcher.enqueued == [run_id]

    async def resume() -> None:
        database = Database(migrated_database_url)
        embeddings = FakeEmbeddingProvider()
        try:
            result = await execute_support_run(
                database,
                run_id=run_id,
                provider=FakeTextProvider(),
                embedding_provider=embeddings,
                observer=NoopAIObserver(),
                model="fake",
            )
            assert result.status == "resumed"
            async with database.session() as session:
                run = await session.get(AgentRun, run_id)
                ticket = await session.scalar(
                    select(Ticket).where(Ticket.approval_id == approval_id)
                )
                receipt_message = await session.scalar(
                    select(Message).where(
                        Message.run_id == run_id,
                        Message.outcome == "ticket_created",
                    )
                )
                assert run is not None and run.status is RunStatus.COMPLETED
                assert ticket is not None
                assert receipt_message is not None
                assert ticket.display_key in receipt_message.content
        finally:
            await embeddings.close()
            await database.close()

    asyncio.run(resume())
