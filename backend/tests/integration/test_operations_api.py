from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.auth.demo_identity import ensure_demo_identity
from app.auth.passwords import hash_password
from app.config import Settings
from app.db import Database
from app.db.models import Department, Ticket, User, UserRole
from app.main import create_app
from app.services.service_status import ServiceStatusService

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


def test_it_queue_transitions_service_status_and_role_scope(
    migrated_database_url: str,
) -> None:
    async def seed() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                employee = await ensure_demo_identity(session, password=PASSWORD)
                finance = Department(key="finance", name="Finance")
                session.add(finance)
                await session.flush()
                it_user = User(
                    email="it.engineering@example.com",
                    display_name="Engineering IT",
                    password_hash=hash_password(PASSWORD),
                    role=UserRole.IT,
                    department_id=employee.department_id,
                    active=True,
                )
                finance_user = User(
                    email="finance-user@example.com",
                    display_name="Finance User",
                    password_hash=hash_password(PASSWORD),
                    role=UserRole.EMPLOYEE,
                    department_id=finance.id,
                    active=True,
                )
                session.add_all([it_user, finance_user])
                await session.flush()
                session.add_all(
                    [
                        Ticket(
                            display_key="IT-OPS-ENG",
                            owner_id=employee.id,
                            department_id=employee.department_id,
                            title="Engineering VPN",
                            description="Engineering user cannot access VPN.",
                            issue_type="vpn",
                            severity="normal",
                            status="open",
                        ),
                        Ticket(
                            display_key="IT-OPS-FIN",
                            owner_id=finance_user.id,
                            department_id=finance.id,
                            title="Finance GitLab",
                            description="Finance user cannot access GitLab.",
                            issue_type="gitlab",
                            severity="low",
                            status="open",
                        ),
                    ]
                )
                await ServiceStatusService().ensure_defaults(session)
        finally:
            await database.close()

    asyncio.run(seed())
    settings = Settings(
        database_url=migrated_database_url,
        auth_login_rate_limit_enabled=False,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )
    with TestClient(create_app(settings=settings), base_url=ORIGIN) as employee_client:
        login = employee_client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        assert login.status_code == 200
        assert employee_client.get("/api/v1/tickets/queue").status_code == 403
        assert employee_client.get("/api/v1/service-status").status_code == 403

    with TestClient(create_app(settings=settings), base_url=ORIGIN) as it_client:
        login = it_client.post(
            "/api/v1/auth/login",
            json={"email": "it.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        csrf = login.json()["csrf_token"]
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        queue = it_client.get("/api/v1/tickets/queue")
        assert queue.status_code == 200
        assert [item["display_key"] for item in queue.json()] == ["IT-OPS-ENG"]
        ticket = queue.json()[0]

        started = it_client.post(
            f"/api/v1/tickets/{ticket['id']}/transition",
            json={"action": "start", "expected_version": ticket["version"]},
            headers=headers,
        )
        assert started.json()["status"] == "in_progress"
        without_note = it_client.post(
            f"/api/v1/tickets/{ticket['id']}/transition",
            json={"action": "resolve", "expected_version": started.json()["version"]},
            headers=headers,
        )
        assert without_note.status_code == 409
        resolved = it_client.post(
            f"/api/v1/tickets/{ticket['id']}/transition",
            json={
                "action": "resolve",
                "expected_version": started.json()["version"],
                "resolution_note": "Reissued the VPN profile and verified connectivity.",
            },
            headers=headers,
        )
        assert resolved.json()["status"] == "resolved"
        reopened = it_client.post(
            f"/api/v1/tickets/{ticket['id']}/transition",
            json={"action": "reopen", "expected_version": resolved.json()["version"]},
            headers=headers,
        )
        assert reopened.json()["status"] == "open"
        assert reopened.json()["resolution_note"] is None

        services = it_client.get("/api/v1/service-status")
        assert services.status_code == 200
        updated = it_client.patch(
            "/api/v1/service-status/vpn",
            json={
                "status": "degraded",
                "message": "VPN latency is elevated in the demo.",
                "fault_mode": "timeout",
            },
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "degraded"
        assert updated.json()["fault_mode"] == "timeout"
