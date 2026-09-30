from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from redis.asyncio import Redis

from app.auth.demo_identity import DEMO_EMAIL, ensure_demo_identity
from app.auth.rate_limit import login_bucket_key
from app.config import Settings
from app.db import Database
from app.main import create_app

PASSWORD = "correct-horse-battery-staple"
ORIGIN = "http://testserver"
CLIENT_IDENTIFIER = "testclient"


def prepare_identity_and_bucket(database_url: str, redis_url: str) -> None:
    async def prepare() -> None:
        database = Database(database_url)
        redis_client: Redis = Redis.from_url(redis_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_identity(session, password=PASSWORD)
            await redis_client.delete(
                login_bucket_key(
                    email=DEMO_EMAIL,
                    client_identifier=CLIENT_IDENTIFIER,
                )
            )
        finally:
            await redis_client.aclose()
            await database.close()

    asyncio.run(prepare())


def clear_bucket(redis_url: str) -> None:
    async def clear() -> None:
        redis_client: Redis = Redis.from_url(redis_url)
        try:
            await redis_client.delete(
                login_bucket_key(
                    email=DEMO_EMAIL,
                    client_identifier=CLIENT_IDENTIFIER,
                )
            )
        finally:
            await redis_client.aclose()

    asyncio.run(clear())


def test_login_rate_limit_resets_on_success_and_returns_retry_after(
    migrated_database_url: str,
    test_redis_url: str,
) -> None:
    prepare_identity_and_bucket(migrated_database_url, test_redis_url)
    settings = Settings(
        database_url=migrated_database_url,
        redis_url=test_redis_url,
        auth_login_rate_limit_enabled=True,
        auth_login_max_attempts=2,
        auth_login_window_seconds=60,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )
    try:
        with TestClient(create_app(settings=settings), base_url=ORIGIN) as client:
            first_failure = client.post(
                "/api/v1/auth/login",
                json={"email": DEMO_EMAIL, "password": "wrong"},
                headers={"Origin": ORIGIN},
            )
            assert first_failure.status_code == 401

            success = client.post(
                "/api/v1/auth/login",
                json={"email": DEMO_EMAIL, "password": PASSWORD},
                headers={"Origin": ORIGIN},
            )
            assert success.status_code == 200

            for _ in range(2):
                response = client.post(
                    "/api/v1/auth/login",
                    json={"email": DEMO_EMAIL, "password": "wrong"},
                    headers={"Origin": ORIGIN},
                )
                assert response.status_code == 401

            blocked = client.post(
                "/api/v1/auth/login",
                json={"email": DEMO_EMAIL, "password": PASSWORD},
                headers={"Origin": ORIGIN},
            )
            assert blocked.status_code == 429
            assert 1 <= int(blocked.headers["Retry-After"]) <= 60
            assert blocked.json()["error"]["code"] == "RATE_LIMITED"
            assert blocked.json()["error"]["message"] == "Too many login attempts"
    finally:
        clear_bucket(test_redis_url)


def test_login_fails_closed_when_rate_limit_redis_is_not_configured(
    migrated_database_url: str,
) -> None:
    settings = Settings(
        database_url=migrated_database_url,
        redis_url=None,
        auth_login_rate_limit_enabled=True,
        cookie_secure=False,
        allowed_web_origin=ORIGIN,
    )

    with TestClient(create_app(settings=settings), base_url=ORIGIN) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": DEMO_EMAIL, "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert response.json()["error"]["message"] == "Authentication protection is unavailable"
