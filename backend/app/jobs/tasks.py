"""Minimal task contracts; production handlers are added with their feature slices."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from uuid import UUID

from celery import shared_task  # type: ignore[import-untyped]

from app.config import Settings
from app.db import Database
from app.jobs.celery_app import celery_app
from app.jobs.dispatch import CeleryRunDispatcher
from app.jobs.reconcile import reconcile_queued_run_dispatches
from app.jobs.worker import execute_support_run
from app.observability import create_ai_observer
from app.providers.factory import create_embedding_provider, create_provider


@shared_task(name="jobs.run_agent")  # type: ignore[untyped-decorator]
def run_agent(run_id: str) -> dict[str, str]:
    """Claim a run and execute the configured retrieval-backed support graph."""

    settings = Settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is required by the agent worker")
    database_url = settings.database_url.get_secret_value()

    async def execute() -> dict[str, str]:
        database = Database(database_url)
        provider = create_provider(settings, database)
        embedding_provider = create_embedding_provider(settings, database)
        observer = create_ai_observer(settings)
        try:
            receipt = asdict(
                await execute_support_run(
                    database,
                    run_id=UUID(run_id),
                    provider=provider,
                    embedding_provider=embedding_provider,
                    observer=observer,
                    model=settings.openai_model
                    if settings.ai_provider.value == "openai"
                    else "fake",
                )
            )
            return {key: str(value) for key, value in receipt.items()}
        finally:
            observer.close()
            await embedding_provider.close()
            await provider.close()
            await database.close()

    return asyncio.run(execute())


@shared_task(name="jobs.reconcile_queued_runs")  # type: ignore[untyped-decorator]
def reconcile_queued_runs() -> dict[str, int]:
    """Re-enqueue old queued runs; duplicate deliveries are claimed in PostgreSQL."""

    settings = Settings()
    if settings.database_url is None or settings.redis_url is None:
        raise RuntimeError("DATABASE_URL and REDIS_URL are required by reconciliation")
    database_url = settings.database_url.get_secret_value()
    redis_url = settings.redis_url.get_secret_value()

    async def reconcile() -> int:
        database = Database(database_url)
        dispatcher = CeleryRunDispatcher(
            celery_app,
            redis_url=redis_url,
            socket_timeout_seconds=settings.redis_socket_timeout_seconds,
        )
        try:
            return await reconcile_queued_run_dispatches(database, dispatcher)
        finally:
            await database.close()

    return {"requeued": asyncio.run(reconcile())}
