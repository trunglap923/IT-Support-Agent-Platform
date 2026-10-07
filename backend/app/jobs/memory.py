"""Durable memory extraction execution and pending-job reconciliation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.db import Database
from app.db.models import AgentRun, IncidentEpisode, MemoryExtractionJob, RunStatus
from app.jobs.dispatch import EpisodeConsolidationDispatcher, MemoryExtractionDispatcher
from app.memory.episodes import EpisodeMemoryService
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


async def execute_episode_consolidation(database: Database, *, run_id: UUID) -> str:
    async with database.session() as session, session.begin():
        episode = await EpisodeMemoryService().consolidate(session, run_id=run_id)
        return "completed" if episode is not None else "not_ready"


async def reconcile_episode_consolidations(
    database: Database,
    dispatcher: EpisodeConsolidationDispatcher,
    *,
    limit: int = 100,
) -> int:
    async with database.session() as session:
        run_ids = list(
            await session.scalars(
                select(AgentRun.id)
                .outerjoin(IncidentEpisode, IncidentEpisode.run_id == AgentRun.id)
                .where(
                    AgentRun.status == RunStatus.COMPLETED,
                    IncidentEpisode.id.is_(None),
                )
                .order_by(AgentRun.finished_at, AgentRun.id)
                .limit(limit)
            )
        )
    for run_id in run_ids:
        await dispatcher.enqueue_episode_consolidation(run_id)
    return len(run_ids)
