from __future__ import annotations

import asyncio
from uuid import uuid4

from redis.asyncio import Redis

from app.config import Settings
from app.jobs.celery_app import AGENT_QUEUE, create_celery_app
from app.jobs.dispatch import CeleryRunDispatcher


def test_real_redis_preflight_and_agent_queue_delivery(test_redis_url: str) -> None:
    redis_url = test_redis_url
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
