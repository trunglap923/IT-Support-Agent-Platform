from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.auth.demo_identity import ensure_demo_identity
from app.config import Settings
from app.db import Database
from app.db.models import AuthSession, User
from app.main import create_app

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"


def seed_identity(database_url: str) -> None:
    async def seed() -> None:
        database = Database(database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_identity(session, password=PASSWORD)
        finally:
            await database.close()

    asyncio.run(seed())


def test_login_me_logout_and_invalid_credentials(migrated_database_url: str) -> None:
    seed_identity(migrated_database_url)
    settings = Settings(
        database_url=migrated_database_url,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )

    with TestClient(create_app(settings=settings)) as client:
        invalid = client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": "wrong"},
            headers={"Origin": ORIGIN},
        )
        assert invalid.status_code == 401
        assert settings.session_cookie_name not in invalid.cookies

        login = client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        assert login.status_code == 200
        assert login.json()["user"]["role"] == "employee"
        assert login.json()["csrf_token"]
        assert settings.session_cookie_name in client.cookies

        current = client.get("/api/v1/auth/me")
        assert current.status_code == 200
        assert current.json()["user"]["department_key"] == "engineering"
        assert current.json()["csrf_token"] == login.json()["csrf_token"]

        client.cookies.delete(settings.csrf_cookie_name)
        client.cookies.set(settings.csrf_cookie_name, "tampered")
        assert client.get("/api/v1/auth/me").status_code == 401
        client.cookies.delete(settings.csrf_cookie_name)
        client.cookies.set(settings.csrf_cookie_name, login.json()["csrf_token"])

        csrf_token = login.json()["csrf_token"]
        logout = client.post(
            "/api/v1/auth/logout",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
        )
        assert logout.status_code == 204
        assert client.get("/api/v1/auth/me").status_code == 401


def test_expired_session_is_rejected(migrated_database_url: str) -> None:
    seed_identity(migrated_database_url)
    settings = Settings(
        database_url=migrated_database_url,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )

    with TestClient(create_app(settings=settings)) as client:
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "employee.engineering@example.com", "password": PASSWORD},
                headers={"Origin": ORIGIN},
            ).status_code
            == 200
        )

        async def expire() -> None:
            database = Database(migrated_database_url)
            try:
                async with database.session() as session, session.begin():
                    await session.execute(
                        update(AuthSession).values(
                            expires_at=datetime.now(UTC) - timedelta(seconds=1)
                        )
                    )
            finally:
                await database.close()

        asyncio.run(expire())
        assert client.get("/api/v1/auth/me").status_code == 401


def test_existing_session_is_rejected_after_account_deactivation(
    migrated_database_url: str,
) -> None:
    seed_identity(migrated_database_url)
    settings = Settings(
        database_url=migrated_database_url,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )

    with TestClient(create_app(settings=settings)) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        assert login.status_code == 200
        assert settings.session_cookie_name in client.cookies

        async def deactivate_account() -> None:
            database = Database(migrated_database_url)
            try:
                async with database.session() as session, session.begin():
                    await session.execute(
                        update(User)
                        .where(User.email == "employee.engineering@example.com")
                        .values(active=False)
                    )
            finally:
                await database.close()

        asyncio.run(deactivate_account())

        assert client.get("/api/v1/auth/me").status_code == 401


def test_csrf_origin_cookie_flags_and_role_denial(migrated_database_url: str) -> None:
    seed_identity(migrated_database_url)
    settings = Settings(
        database_url=migrated_database_url,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )

    with TestClient(create_app(settings=settings)) as client:
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "employee.engineering@example.com", "password": PASSWORD},
            ).status_code
            == 403
        )
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        assert login.status_code == 200
        set_cookie = login.headers.get_list("set-cookie")
        session_cookie = next(
            value for value in set_cookie if value.startswith(settings.session_cookie_name)
        )
        assert "HttpOnly" in session_cookie
        assert "SameSite=lax" in session_cookie

        assert client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN}).status_code == 403
        assert (
            client.post(
                "/api/v1/auth/logout",
                headers={"Origin": ORIGIN, "X-CSRF-Token": "wrong"},
            ).status_code
            == 403
        )
        assert client.get("/api/v1/auth/admin-check").status_code == 403


def test_secure_cookie_flags_when_enabled(migrated_database_url: str) -> None:
    secure_origin = "https://testserver"
    seed_identity(migrated_database_url)
    settings = Settings(
        database_url=migrated_database_url,
        cookie_secure=True,
        allowed_web_origin=secure_origin,
    )

    with TestClient(
        create_app(settings=settings),
        base_url=secure_origin,
    ) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "employee.engineering@example.com", "password": PASSWORD},
            headers={"Origin": secure_origin},
        )
        assert login.status_code == 200
        set_cookie = login.headers.get_list("set-cookie")
        session_cookie = next(
            value for value in set_cookie if value.startswith(settings.session_cookie_name)
        )
        csrf_cookie = next(
            value for value in set_cookie if value.startswith(settings.csrf_cookie_name)
        )
        assert "Secure" in session_cookie
        assert "HttpOnly" in session_cookie
        assert "SameSite=lax" in session_cookie
        assert "Secure" in csrf_cookie
        assert "HttpOnly" not in csrf_cookie
