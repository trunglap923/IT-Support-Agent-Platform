"""Validated run transitions persisted with an event in the same transaction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRun, RunEvent, RunStatus
from app.repositories.runs import RunRepository

TERMINAL_RUN_STATUSES = frozenset({RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED})
ALLOWED_RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.QUEUED: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    RunStatus.RUNNING: frozenset(
        {RunStatus.WAITING_APPROVAL, RunStatus.COMPLETED, RunStatus.FAILED}
    ),
    RunStatus.WAITING_APPROVAL: frozenset(
        {RunStatus.RESUME_QUEUED, RunStatus.COMPLETED, RunStatus.CANCELLED}
    ),
    RunStatus.RESUME_QUEUED: frozenset({RunStatus.RUNNING, RunStatus.FAILED}),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}


class RunNotFoundError(LookupError):
    pass


class InvalidRunTransitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TransitionResult:
    run: AgentRun
    event: RunEvent
    applied: bool


def validate_run_transition(current: RunStatus, target: RunStatus) -> None:
    if target not in ALLOWED_RUN_TRANSITIONS[current]:
        raise InvalidRunTransitionError(f"Cannot transition run from {current} to {target}")


class RunStateService:
    def __init__(self, repository: RunRepository | None = None) -> None:
        self.repository = repository or RunRepository()

    async def transition(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        actor_id: UUID,
        target: RunStatus,
        operation_id: str,
        safe_payload: dict[str, Any] | None = None,
        outcome: str | None = None,
        error_code: str | None = None,
        now: datetime | None = None,
    ) -> TransitionResult:
        run = await self.repository.get_owned_for_update(
            session,
            run_id=run_id,
            actor_id=actor_id,
        )
        if run is None:
            raise RunNotFoundError("Run was not found")

        existing_event = await self.repository.get_event_by_dedupe_key(
            session,
            run_id=run_id,
            dedupe_key=operation_id,
        )
        if existing_event is not None:
            return TransitionResult(run=run, event=existing_event, applied=False)

        validate_run_transition(run.status, target)
        changed_at = now or datetime.now(UTC)
        run.status = target
        run.version += 1
        run.outcome = outcome
        run.error_code = error_code
        run.finished_at = changed_at if target in TERMINAL_RUN_STATUSES else None
        event = await self.repository.append_event(
            session,
            run_id=run.id,
            event_type=f"run.{target.value}",
            dedupe_key=operation_id,
            safe_payload=safe_payload or {},
        )
        await session.flush()
        return TransitionResult(run=run, event=event, applied=True)
