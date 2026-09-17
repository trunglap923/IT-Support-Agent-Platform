"""Durable memory extraction execution and pending-job reconciliation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.db import Database
from app.db.models import MemoryExtractionJob
from app.jobs.dispatch import MemoryExtractionDispatcher
from app.memory.lifecycle import MemoryLifecycleService


async def execute_memory_extraction(database: Database, *, job_id: UUID) -> str:
    async with database.session() as session, session.begin():
        job = await session.get(MemoryExtractionJob, job_id)
        if job is None:
            return "missing"
        result = await MemoryLifecycleService().complete_extraction_job(
            session,
            owner_id=job.owner_id,
            job_id=job.id,
        )
        return result.job.status


async def reconcile_memory_extractions(
    database: Database,
    dispatcher: MemoryExtractionDispatcher,
    *,
    limit: int = 100,
) -> int:
    """Redeliver pending IDs; row locking in completion makes duplicates harmless."""

    async with database.session() as session:
        job_ids = list(
            await session.scalars(
                select(MemoryExtractionJob.id)
                .where(MemoryExtractionJob.status == "pending")
                .order_by(MemoryExtractionJob.created_at, MemoryExtractionJob.id)
                .limit(limit)
            )
        )
    delivered = 0
    for job_id in job_ids:
        await dispatcher.enqueue_memory_extraction(job_id)
        delivered += 1
    return delivered
