"""Broker boundary for preflight checks and stable run delivery."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol
from uuid import UUID

from redis.asyncio import Redis

from app.jobs.celery_app import AGENT_QUEUE


class BrokerUnavailableError(RuntimeError):
    pass


class RunDispatcher(Protocol):
    async def ensure_available(self) -> None: ...

    async def enqueue_run(self, run_id: UUID) -> None: ...


class UnavailableRunDispatcher:
    async def ensure_available(self) -> None:
        raise BrokerUnavailableError("Redis broker is not configured")

    async def enqueue_run(self, run_id: UUID) -> None:
        del run_id
        raise BrokerUnavailableError("Redis broker is not configured")


class CeleryRunDispatcher:
    def __init__(
        self,
        celery_application: Any,
        *,
        redis_url: str,
        socket_timeout_seconds: float,
    ) -> None:
        self.celery_application = celery_application
        self.redis_url = redis_url
        self.socket_timeout_seconds = socket_timeout_seconds

    async def ensure_available(self) -> None:
        client: Redis = Redis.from_url(
            self.redis_url,
            socket_connect_timeout=self.socket_timeout_seconds,
            socket_timeout=self.socket_timeout_seconds,
        )
        try:
            await client.ping()
        except Exception as error:
            raise BrokerUnavailableError("Redis broker is unavailable") from error
        finally:
            await client.aclose()

    async def enqueue_run(self, run_id: UUID) -> None:
        try:
            await asyncio.to_thread(
                self.celery_application.send_task,
                "jobs.run_agent",
                args=[str(run_id)],
                task_id=f"agent-run:{run_id}",
                queue=AGENT_QUEUE,
            )
        except Exception as error:
            raise BrokerUnavailableError("Run enqueue failed") from error
