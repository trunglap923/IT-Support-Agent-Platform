"""Worker-side run claim using PostgreSQL state for duplicate delivery safety."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.db import Database
from app.db.models import RunStatus
from app.repositories.runs import RunRepository
from app.services.conversations.run_state import RunStateService


@dataclass(frozen=True, slots=True)
class WorkerResult:
    run_id: UUID
    status: str


async def execute_fake_run(database: Database, *, run_id: UUID) -> WorkerResult:
    repository = RunRepository()
    async with database.session() as session:
        run = await repository.get_by_id(session, run_id=run_id)
        if run is None:
            return WorkerResult(run_id=run_id, status="missing")
        actor_id = run.actor_id

    state = RunStateService(repository)
    async with database.session() as session, session.begin():
        claimed = await state.transition(
            session,
            run_id=run_id,
            actor_id=actor_id,
            target=RunStatus.RUNNING,
            operation_id=f"worker-claim:{run_id}",
        )
        if not claimed.applied:
            return WorkerResult(run_id=run_id, status="duplicate")

    async with database.session() as session, session.begin():
        await state.transition(
            session,
            run_id=run_id,
            actor_id=actor_id,
            target=RunStatus.COMPLETED,
            operation_id=f"worker-complete:{run_id}",
            outcome="answered",
            safe_payload={"provider": "fake"},
        )
    return WorkerResult(run_id=run_id, status="processed")
