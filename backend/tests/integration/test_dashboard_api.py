from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.demo_identity import ensure_demo_accounts
from app.config import Settings
from app.db import Database
from app.db.models import Ticket, TicketEvent, User
from app.demo_seed import ensure_demo_devices_and_service_states
from app.main import create_app

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


def test_dashboard_is_role_scoped_and_supports_both_ranges(
    migrated_database_url: str,
) -> None:
    async def seed() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_accounts(session, password=PASSWORD)
                await ensure_demo_devices_and_service_states(session)
                users = {
                    user.email: user
                    for user in (
                        await session.scalars(
                            select(User).where(
                                User.email.in_(
                                    [
                                        "employee.engineering@example.com",
                                        "employee.engineering.second@example.com",
                                        "employee.operations@example.com",
                                    ]
                                )
                            )
                        )
                    ).all()
                }
                now = datetime.now(UTC)
                personal = Ticket(
                    display_key="DASH-ENG-1",
                    owner_id=users["employee.engineering@example.com"].id,
                    department_id=users["employee.engineering@example.com"].department_id,
                    title="VPN cá nhân",
                    description="Không thể kết nối VPN.",
                    issue_type="vpn",
                    severity="high",
                    status="open",
                    created_at=now - timedelta(days=2),
                    updated_at=now - timedelta(days=2),
                )
                department = Ticket(
                    display_key="DASH-ENG-2",
                    owner_id=users["employee.engineering.second@example.com"].id,
                    department_id=users["employee.engineering.second@example.com"].department_id,
                    title="Docker cùng phòng ban",
                    description="Registry không phản hồi.",
                    issue_type="docker",
                    severity="normal",
                    status="in_progress",
                    created_at=now - timedelta(days=10),
                    updated_at=now - timedelta(days=1),
                )
                outside = Ticket(
                    display_key="DASH-OPS-1",
                    owner_id=users["employee.operations@example.com"].id,
                    department_id=users["employee.operations@example.com"].department_id,
                    title="GitLab ngoài phòng ban",
                    description="Không thể clone repository.",
                    issue_type="gitlab",
                    severity="low",
                    status="open",
                    created_at=now - timedelta(days=1),
                    updated_at=now - timedelta(days=1),
                )
                session.add_all([personal, department, outside])
                await session.flush()
                session.add(
                    TicketEvent(
                        ticket_id=department.id,
                        actor_id=users["employee.engineering.second@example.com"].id,
                        type="ticket.in_progress",
                        safe_payload={},
                        created_at=now - timedelta(days=1),
                    )
                )
        finally:
            await database.close()

    asyncio.run(seed())
    settings = Settings(
        database_url=migrated_database_url,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )

    def dashboard(email: str, days: int) -> dict[str, object]:
        with TestClient(create_app(settings=settings), base_url=ORIGIN) as client:
            login = client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": PASSWORD},
                headers={"Origin": ORIGIN},
            )
            assert login.status_code == 200
            response = client.get(f"/api/v1/dashboard?range_days={days}")
            assert response.status_code == 200
            return response.json()

    employee = dashboard("employee.engineering@example.com", 7)
    assert employee["scope"] == "personal"
    assert [item["display_key"] for item in employee["attention_tickets"]] == ["DASH-ENG-1"]
    assert sum(item["created"] for item in employee["daily_activity"]) == 1

    it_dashboard = dashboard("it.engineering@example.com", 30)
    assert it_dashboard["scope"] == "department"
    assert {item["display_key"] for item in it_dashboard["attention_tickets"]} == {
        "DASH-ENG-1",
        "DASH-ENG-2",
    }
    assert sum(item["started"] for item in it_dashboard["daily_activity"]) == 1

    admin = dashboard("admin@example.com", 7)
    assert admin["scope"] == "global"
    assert {item["display_key"] for item in admin["attention_tickets"]} == {
        "DASH-ENG-1",
        "DASH-ENG-2",
        "DASH-OPS-1",
    }
    assert len(admin["daily_activity"]) == 7
    assert len(admin["services"]) == 3


def test_dashboard_rejects_unsupported_range(migrated_database_url: str) -> None:
    async def seed() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_accounts(session, password=PASSWORD)
        finally:
            await database.close()

    asyncio.run(seed())
    settings = Settings(
        database_url=migrated_database_url,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )
    with TestClient(create_app(settings=settings), base_url=ORIGIN) as client:
        client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        assert client.get("/api/v1/dashboard?range_days=14").status_code == 422
