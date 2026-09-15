from __future__ import annotations

import asyncio
import os
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.config import Settings
from app.jobs.celery_app import AGENT_QUEUE, create_celery_app
from app.jobs.dispatch import CeleryRunDispatcher


def required_test_redis_url() -> str:
    configured = os.getenv("TEST_REDIS_URL")
    if configured:
        if urlsplit(configured).path in {"", "/", "/0"}:
            pytest.fail("TEST_REDIS_URL must use a dedicated non-zero Redis database")
        return configured
    if os.getenv("REQUIRE_REDIS_TESTS") == "1":
        pytest.fail("Set TEST_REDIS_URL before the required Redis integration gate")
    pytest.skip("TEST_REDIS_URL is not configured")


def test_real_redis_preflight_and_agent_queue_delivery() -> None:
    redis_url = required_test_redis_url()
    application = create_celery_app(Settings(redis_url=redis_url))
    dispatcher = CeleryRunDispatcher(
        application,
        redis_url=redis_url,
        socket_timeout_seconds=2,
    )
    run_id = uuid4()

    async def scenario() -> None:
        client: Redis = Redis.from_url(redis_url)
        try:
            await client.delete(AGENT_QUEUE)
            await dispatcher.ensure_available()
            await dispatcher.enqueue_run(run_id)
            assert await client.llen(AGENT_QUEUE) == 1
        finally:
            await client.delete(AGENT_QUEUE)
            await client.aclose()

    try:
        asyncio.run(scenario())
    finally:
        application.close()
