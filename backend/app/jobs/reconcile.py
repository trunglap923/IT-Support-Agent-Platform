"""Re-enqueue committed runs that have remained queued without a worker claim."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db import Database
from app.jobs.dispatch import BrokerUnavailableError, RunDispatcher
from app.repositories.runs import RunRepository


async def reconcile_queued_run_dispatches(
    database: Database,
    dispatcher: RunDispatcher,
    *,
    older_than_seconds: int = 30,
    max_attempts: int = 3,
    limit: int = 100,
) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
    async with database.session() as session:
        queued_runs = await RunRepository().list_recoverable(
            session,
            queued_before=cutoff,
            now=datetime.now(UTC),
            max_attempts=max_attempts,
            limit=limit,
        )

    requeued = 0
    for run in queued_runs:
        try:
            await dispatcher.enqueue_run(run.id)
        except BrokerUnavailableError:
            break
        requeued += 1
    return requeued
