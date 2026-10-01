from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi.testclient import TestClient

from app.auth.demo_identity import ensure_demo_identity
from app.config import Settings
from app.db import Database
from app.main import create_app

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


class RecordingDispatcher:
    def __init__(self) -> None:
        self.enqueued: list[UUID] = []

    async def ensure_available(self) -> None:
        return None

    async def enqueue_run(self, run_id: UUID) -> None:
        self.enqueued.append(run_id)


def seed(database_url: str) -> None:
    async def execute() -> None:
        database = Database(database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_identity(session, password=PASSWORD)
        finally:
            await database.close()

    asyncio.run(execute())


def test_chat_api_creates_conversation_and_enqueues_owned_run(
    migrated_database_url: str,
) -> None:
    seed(migrated_database_url)
    dispatcher = RecordingDispatcher()
    settings = Settings(
        database_url=migrated_database_url,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )
    with TestClient(
        create_app(settings=settings, run_dispatcher=dispatcher), base_url=ORIGIN
    ) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        csrf = login.json()["csrf_token"]
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        created = client.post("/api/v1/conversations", json={"title": "VPN help"}, headers=headers)
        assert created.status_code == 201
        conversation_id = created.json()["id"]

        submitted = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"content": "How do I connect?", "client_request_id": "request-0001"},
            headers=headers,
        )
        assert submitted.status_code == 202
        assert submitted.json()["status"] == "queued"
        assert dispatcher.enqueued == [UUID(submitted.json()["run_id"])]
        messages = client.get(f"/api/v1/conversations/{conversation_id}/messages").json()["items"]
        assert [(message["role"], message["content"]) for message in messages] == [
            ("user", "How do I connect?")
        ]

        conversation_page = client.get("/api/v1/conversations").json()
        listed_conversation = conversation_page["items"][0]
        assert listed_conversation["id"] == conversation_id
        assert listed_conversation["title"] == "VPN help"
        assert listed_conversation["preview"] == "How do I connect?"
        assert listed_conversation["preview_role"] == "user"
        assert listed_conversation["preview_at"] is not None
        assert listed_conversation["updated_at"] is not None
        assert listed_conversation["created_at"] is not None
        assert listed_conversation["device_id"] is None
        assert conversation_page["next_cursor"] is None

        for title in ("Docker help", "GitLab help"):
            assert (
                client.post(
                    "/api/v1/conversations", json={"title": title}, headers=headers
                ).status_code
                == 201
            )
        first_page = client.get("/api/v1/conversations?limit=2").json()
        assert len(first_page["items"]) == 2
        assert first_page["next_cursor"] is not None
        second_page = client.get(
            "/api/v1/conversations",
            params={"limit": 2, "cursor": first_page["next_cursor"]},
        ).json()
        assert len(second_page["items"]) == 1
        assert second_page["next_cursor"] is None
        assert {item["id"] for item in first_page["items"]}.isdisjoint(
            item["id"] for item in second_page["items"]
        )
        invalid = client.get("/api/v1/conversations?cursor=not-a-cursor")
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "INVALID_CURSOR"


def test_chat_api_hides_another_users_conversation(migrated_database_url: str) -> None:
    seed(migrated_database_url)
    dispatcher = RecordingDispatcher()
    settings = Settings(
        database_url=migrated_database_url,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )
    with TestClient(
        create_app(settings=settings, run_dispatcher=dispatcher), base_url=ORIGIN
    ) as owner:
        login = owner.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        csrf = login.json()["csrf_token"]
        conversation_id = owner.post(
            "/api/v1/conversations",
            json={"title": "Private"},
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        ).json()["id"]

    # An unauthenticated caller must not be able to distinguish ownership.
    with TestClient(
        create_app(settings=settings, run_dispatcher=dispatcher), base_url=ORIGIN
    ) as outsider:
        assert outsider.get(f"/api/v1/conversations/{conversation_id}/messages").status_code == 401
