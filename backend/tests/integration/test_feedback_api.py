from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth.demo_identity import ensure_demo_identity
from app.auth.passwords import hash_password
from app.config import Settings
from app.db import Database
from app.db.models import Conversation, Department, Message, MessageFeedback, User, UserRole
from app.main import create_app

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


@dataclass(frozen=True)
class FeedbackFixture:
    conversation_id: UUID
    assistant_message_id: UUID
    user_message_id: UUID
    other_conversation_id: UUID
    other_assistant_message_id: UUID


def seed_feedback(database_url: str) -> FeedbackFixture:
    async def execute() -> FeedbackFixture:
        database = Database(database_url)
        try:
            async with database.session() as session, session.begin():
                owner = await ensure_demo_identity(session, password=PASSWORD)
                department = await session.scalar(
                    select(Department).where(Department.key == "engineering")
                )
                assert department is not None
                other = User(
                    email="feedback.other@example.com",
                    display_name="Other employee",
                    password_hash=hash_password(PASSWORD),
                    role=UserRole.EMPLOYEE,
                    department_id=department.id,
                    active=True,
                )
                session.add(other)
                await session.flush()
                conversation = Conversation(owner_id=owner.id, title="Owner", issue_state={})
                other_conversation = Conversation(owner_id=other.id, title="Other", issue_state={})
                session.add_all([conversation, other_conversation])
                await session.flush()
                assistant = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content="Use the managed VPN client.",
                    citations=[],
                )
                user_message = Message(
                    conversation_id=conversation.id,
                    role="user",
                    content="VPN help",
                    citations=[],
                )
                other_assistant = Message(
                    conversation_id=other_conversation.id,
                    role="assistant",
                    content="Private response",
                    citations=[],
                )
                session.add_all([assistant, user_message, other_assistant])
                await session.flush()
                return FeedbackFixture(
                    conversation_id=conversation.id,
                    assistant_message_id=assistant.id,
                    user_message_id=user_message.id,
                    other_conversation_id=other_conversation.id,
                    other_assistant_message_id=other_assistant.id,
                )
        finally:
            await database.close()

    return asyncio.run(execute())


def login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "employee.engineering@example.com", "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_feedback_is_idempotent_csrf_protected_and_owner_scoped(
    migrated_database_url: str,
) -> None:
    fixture = seed_feedback(migrated_database_url)
    settings = Settings(
        database_url=migrated_database_url,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )
    endpoint = (
        f"/api/v1/conversations/{fixture.conversation_id}/messages/"
        f"{fixture.assistant_message_id}/feedback"
    )
    with TestClient(create_app(settings=settings), base_url=ORIGIN) as client:
        csrf = login(client)
        assert client.put(endpoint, json={"rating": "helpful"}).status_code == 403
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}

        created = client.put(endpoint, json={"rating": "helpful"}, headers=headers)
        assert created.status_code == 200
        feedback_id = created.json()["id"]
        updated = client.put(
            endpoint,
            json={"rating": "unhelpful", "reason": "missing_step"},
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json() == {
            "id": feedback_id,
            "message_id": str(fixture.assistant_message_id),
            "rating": "unhelpful",
            "reason": "missing_step",
            "comment": None,
        }

        messages = client.get(f"/api/v1/conversations/{fixture.conversation_id}/messages").json()[
            "items"
        ]
        assistant = next(item for item in messages if item["role"] == "assistant")
        assert assistant["feedback"]["rating"] == "unhelpful"

        user_target = (
            f"/api/v1/conversations/{fixture.conversation_id}/messages/"
            f"{fixture.user_message_id}/feedback"
        )
        assert (
            client.put(user_target, json={"rating": "helpful"}, headers=headers).status_code == 404
        )
        other_target = (
            f"/api/v1/conversations/{fixture.other_conversation_id}/messages/"
            f"{fixture.other_assistant_message_id}/feedback"
        )
        assert (
            client.put(other_target, json={"rating": "helpful"}, headers=headers).status_code == 404
        )

    async def assert_single_row() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session:
                count = await session.scalar(select(func.count()).select_from(MessageFeedback))
                assert count == 1
        finally:
            await database.close()

    asyncio.run(assert_single_row())
