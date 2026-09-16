"""Database-owned worker leases for crash-safe run execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRun, RunStatus
from app.repositories.runs import RunRepository

LeaseOutcome = Literal["claimed", "reclaimed", "busy", "missing", "exhausted"]


@dataclass(frozen=True, slots=True)
class RunLeaseClaim:
    outcome: LeaseOutcome
    run: AgentRun | None
    previous_status: RunStatus | None

    @property
    def acquired(self) -> bool:
        return self.outcome in {"claimed", "reclaimed"}


class RunLeaseService:
    def __init__(self, repository: RunRepository | None = None) -> None:
        self.repository = repository or RunRepository()

    async def claim(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        worker_id: str,
        lease_seconds: int,
        max_attempts: int,
        now: datetime | None = None,
    ) -> RunLeaseClaim:
        current = now or datetime.now(UTC)
        run = await self.repository.get_for_update(session, run_id=run_id)
        if run is None:
            return RunLeaseClaim("missing", None, None)
        previous_status = run.status
        fresh = previous_status in {RunStatus.QUEUED, RunStatus.RESUME_QUEUED}
        stale = (
            previous_status is RunStatus.RUNNING
            and run.lease_until is not None
            and run.lease_until <= current
        )
        if not fresh and not stale:
            return RunLeaseClaim("busy", run, previous_status)
        if run.attempts >= max_attempts:
            run.status = RunStatus.FAILED
            run.error_code = "recovery_attempts_exhausted"
            run.finished_at = current
            run.lease_owner = None
            run.lease_until = None
            run.version += 1
            await self.repository.append_event(
                session,
                run_id=run.id,
                event_type="run.failed",
                dedupe_key=f"lease-exhausted:{run.id}",
                safe_payload={"error_code": "recovery_attempts_exhausted"},
            )
            await session.flush()
            return RunLeaseClaim("exhausted", run, previous_status)
        run.lease_owner = worker_id
        run.lease_until = current + timedelta(seconds=lease_seconds)
        run.attempts += 1
        run.execution_version += 1
        await session.flush()
        return RunLeaseClaim("reclaimed" if stale else "claimed", run, previous_status)

    async def heartbeat(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        worker_id: str,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> bool:
        run = await self.repository.get_for_update(session, run_id=run_id)
        if run is None or run.status is not RunStatus.RUNNING or run.lease_owner != worker_id:
            return False
        run.lease_until = (now or datetime.now(UTC)) + timedelta(seconds=lease_seconds)
        await session.flush()
        return True
