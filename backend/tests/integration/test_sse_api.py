from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.runs import encode_sse_heartbeat, resolve_event_cursor
from app.auth.passwords import hash_password
from app.config import Settings
from app.db import Database
from app.db.models import (
    AgentRun,
    Department,
    Message,
    RunEvent,
    RunKind,
    RunStatus,
    User,
    UserRole,
)
from app.main import create_app
from app.repositories.conversations import ConversationRepository

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


def test_sse_cursor_and_heartbeat_contract() -> None:
    assert resolve_event_cursor(None, 4) == 4
    assert resolve_event_cursor("7", 4) == 7
    assert encode_sse_heartbeat() == ": heartbeat\n\n"


def seed_terminal_run(database_url: str) -> tuple[str, str, str]:
    async def seed() -> tuple[str, str, str]:
        database = Database(database_url)
        try:
            async with database.session() as session, session.begin():
                department = Department(key="engineering", name="Engineering")
                session.add(department)
                await session.flush()
                owner = User(
                    email="sse-owner@example.com",
                    display_name="SSE Owner",
                    password_hash=hash_password(PASSWORD),
                    role=UserRole.EMPLOYEE,
                    department_id=department.id,
                    active=True,
                    memory_enabled=False,
                    memory_epoch=0,
                )
                outsider = User(
                    email="sse-outsider@example.com",
                    display_name="SSE Outsider",
                    password_hash=hash_password(PASSWORD),
                    role=UserRole.EMPLOYEE,
                    department_id=department.id,
                    active=True,
                    memory_enabled=False,
                    memory_epoch=0,
                )
                session.add_all([owner, outsider])
                await session.flush()
                conversation = await ConversationRepository().create(
                    session,
                    owner_id=owner.id,
                    title="SSE replay",
                )
                run = AgentRun(
                    conversation_id=conversation.id,
                    actor_id=owner.id,
                    kind=RunKind.CHAT,
                    client_request_id="sse-request",
                    input_hash="d" * 64,
                    status=RunStatus.COMPLETED,
                    outcome="answered",
                    checkpoint_thread_id=str(uuid4()),
                    prompt_version="v1",
                    model="fake",
                    counters={},
                    finished_at=datetime.now(UTC),
                )
                session.add(run)
                await session.flush()
                session.add_all(
                    [
                        RunEvent(
                            run_id=run.id,
                            sequence=sequence,
                            type=event_type,
                            dedupe_key=f"event-{sequence}",
                            safe_payload={"step": sequence},
                        )
                        for sequence, event_type in (
                            (1, "run.queued"),
                            (2, "run.running"),
                            (3, "run.completed"),
                        )
                    ]
                )
                return str(run.id), owner.email, outsider.email
        finally:
            await database.close()

    return asyncio.run(seed())


def count_run_records(database_url: str) -> tuple[int, int, int]:
    async def count() -> tuple[int, int, int]:
        database = Database(database_url)
        try:
            async with database.session() as session:
                runs = await session.scalar(select(func.count()).select_from(AgentRun))
                messages = await session.scalar(select(func.count()).select_from(Message))
                events = await session.scalar(select(func.count()).select_from(RunEvent))
                return int(runs or 0), int(messages or 0), int(events or 0)
        finally:
            await database.close()

    return asyncio.run(count())


def login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200


def test_sse_replay_cursor_ownership_and_no_side_effects(
    migrated_database_url: str,
) -> None:
    run_id, owner_email, outsider_email = seed_terminal_run(migrated_database_url)
    settings = Settings(
        database_url=migrated_database_url,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
        sse_poll_interval_seconds=0.01,
        sse_heartbeat_seconds=0.02,
    )
    before = count_run_records(migrated_database_url)

    with TestClient(create_app(settings=settings), base_url=ORIGIN) as client:
        login(client, owner_email)
        snapshot = client.get(f"/api/v1/runs/{run_id}")
        assert snapshot.status_code == 200
        assert snapshot.json()["status"] == "completed"

        initial = client.get(f"/api/v1/runs/{run_id}/events")
        assert initial.status_code == 200
        assert initial.headers["content-type"].startswith("text/event-stream")
        assert initial.headers["x-accel-buffering"] == "no"
        assert "id: 1\n" in initial.text
        assert "event: run.completed\n" in initial.text

        reconnect = client.get(
            f"/api/v1/runs/{run_id}/events",
            headers={"Last-Event-ID": "1"},
        )
        assert "id: 1\n" not in reconnect.text
        assert "id: 2\n" in reconnect.text
        assert "id: 3\n" in reconnect.text

        query_cursor = client.get(f"/api/v1/runs/{run_id}/events?after_sequence=2")
        assert "id: 2\n" not in query_cursor.text
        assert "id: 3\n" in query_cursor.text

        invalid_cursor = client.get(
            f"/api/v1/runs/{run_id}/events",
            headers={"Last-Event-ID": "not-a-number"},
        )
        assert invalid_cursor.status_code == 422

    with TestClient(create_app(settings=settings), base_url=ORIGIN) as outsider_client:
        login(outsider_client, outsider_email)
        assert outsider_client.get(f"/api/v1/runs/{run_id}").status_code == 404
        assert outsider_client.get(f"/api/v1/runs/{run_id}/events").status_code == 404

    assert count_run_records(migrated_database_url) == before
