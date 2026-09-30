from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth.demo_identity import ensure_demo_accounts, ensure_demo_identity
from app.config import Settings
from app.db import Database
from app.db.models import AgentRun, ApprovalRequest, Conversation, User, UserDevice
from app.demo_seed import ensure_demo_devices_and_service_states
from app.main import create_app
from app.services.approvals import execute_approval_resume_run

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


class RecordingDispatcher:
    def __init__(self) -> None:
        self.enqueued: list[UUID] = []

    async def ensure_available(self) -> None:
        return None

    async def enqueue_run(self, run_id: UUID) -> None:
        self.enqueued.append(run_id)


def test_manual_ticket_draft_approval_and_personal_list(
    migrated_database_url: str,
) -> None:
    async def seed() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_identity(session, password=PASSWORD)
        finally:
            await database.close()

    asyncio.run(seed())
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
        headers = {
            "Origin": ORIGIN,
            "X-CSRF-Token": login.json()["csrf_token"],
        }
        draft_payload = {
            "title": "VPN access is unavailable",
            "description": "VPN remains unavailable after documented troubleshooting.",
            "issue_type": "vpn",
            "severity": "normal",
            "device_id": None,
            "client_request_id": "manual-ticket-0001",
        }
        draft = client.post("/api/v1/tickets/drafts", json=draft_payload, headers=headers)
        assert draft.status_code == 201
        approval = draft.json()["approval"]
        assert approval["status"] == "pending"
        assert (
            client.post("/api/v1/tickets/drafts", json=draft_payload, headers=headers).json()[
                "created"
            ]
            is False
        )
        assert [
            item["id"]
            for item in client.get("/api/v1/approvals?approval_status=pending").json()["items"]
        ] == [approval["id"]]

        approved = client.post(
            f"/api/v1/approvals/{approval['id']}/decision",
            json={"decision": "approve", "expected_version": 1},
            headers=headers,
        )
        assert approved.status_code == 200
        assert dispatcher.enqueued == [UUID(draft.json()["run_id"])]

        async def resume() -> None:
            database = Database(migrated_database_url)
            try:
                assert (
                    await execute_approval_resume_run(database, run_id=UUID(draft.json()["run_id"]))
                    == "resumed"
                )
            finally:
                await database.close()

        asyncio.run(resume())
        tickets = client.get("/api/v1/tickets/mine")
        assert tickets.status_code == 200
        assert [(item["title"], item["status"]) for item in tickets.json()["items"]] == [
            ("VPN access is unavailable", "open")
        ]


def test_manual_ticket_draft_rejects_device_owned_by_another_user(
    migrated_database_url: str,
) -> None:
    async def seed() -> UUID:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_accounts(session, password=PASSWORD)
                await ensure_demo_devices_and_service_states(session)
                other_owner_id = await session.scalar(
                    select(User.id).where(User.email == "employee.operations@example.com")
                )
                assert other_owner_id is not None
                device_id = await session.scalar(
                    select(UserDevice.id).where(UserDevice.owner_id == other_owner_id)
                )
                assert device_id is not None
                return device_id
        finally:
            await database.close()

    wrong_owner_device_id = asyncio.run(seed())
    settings = Settings(
        database_url=migrated_database_url,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )
    with TestClient(create_app(settings=settings), base_url=ORIGIN) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        response = client.post(
            "/api/v1/tickets/drafts",
            json={
                "title": "Wrong device must be rejected",
                "description": "This device belongs to another demo user.",
                "issue_type": "other",
                "severity": "normal",
                "device_id": str(wrong_owner_device_id),
                "client_request_id": "wrong-owner-device-0001",
            },
            headers={
                "Origin": ORIGIN,
                "X-CSRF-Token": login.json()["csrf_token"],
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["message"] == (
            "Device is unavailable for the approval owner"
        )

    async def assert_no_partial_draft() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session:
                for model in (Conversation, AgentRun, ApprovalRequest):
                    assert await session.scalar(select(func.count()).select_from(model)) == 0
        finally:
            await database.close()

    asyncio.run(assert_no_partial_draft())
