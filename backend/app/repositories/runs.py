"""Owner-scoped run and event queries."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRun, RunEvent, RunStatus


class RunRepository:
    async def get_for_update(self, session: AsyncSession, *, run_id: UUID) -> AgentRun | None:
        statement = select(AgentRun).where(AgentRun.id == run_id).with_for_update()
        return cast(AgentRun | None, await session.scalar(statement))

    async def get_by_id(self, session: AsyncSession, *, run_id: UUID) -> AgentRun | None:
        return await session.get(AgentRun, run_id)

    async def get_by_client_request(
        self,
        session: AsyncSession,
        *,
        actor_id: UUID,
        client_request_id: str,
    ) -> AgentRun | None:
        statement = select(AgentRun).where(
            AgentRun.actor_id == actor_id,
            AgentRun.client_request_id == client_request_id,
        )
        return cast(AgentRun | None, await session.scalar(statement))

    async def get_owned(
        self, session: AsyncSession, *, run_id: UUID, actor_id: UUID
    ) -> AgentRun | None:
        statement = select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.actor_id == actor_id,
        )
        return cast(AgentRun | None, await session.scalar(statement))

    async def get_owned_for_update(
        self, session: AsyncSession, *, run_id: UUID, actor_id: UUID
    ) -> AgentRun | None:
        statement = (
            select(AgentRun)
            .where(AgentRun.id == run_id, AgentRun.actor_id == actor_id)
            .with_for_update()
        )
        return cast(AgentRun | None, await session.scalar(statement))

    async def get_event_by_dedupe_key(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        dedupe_key: str,
    ) -> RunEvent | None:
        statement = select(RunEvent).where(
            RunEvent.run_id == run_id,
            RunEvent.dedupe_key == dedupe_key,
        )
        return cast(RunEvent | None, await session.scalar(statement))

    async def append_event(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        event_type: str,
        dedupe_key: str | None,
        safe_payload: dict[str, object],
    ) -> RunEvent:
        last_sequence = await session.scalar(
            select(func.max(RunEvent.sequence)).where(RunEvent.run_id == run_id)
        )
        event = RunEvent(
            run_id=run_id,
            sequence=(last_sequence or 0) + 1,
            type=event_type,
            dedupe_key=dedupe_key,
            safe_payload=safe_payload,
        )
        session.add(event)
        await session.flush()
        return event

    async def list_queued_before(
        self,
        session: AsyncSession,
        *,
        before: datetime,
        limit: int,
    ) -> list[AgentRun]:
        statement = (
            select(AgentRun)
            .where(
                AgentRun.status == RunStatus.QUEUED,
                AgentRun.created_at < before,
            )
            .order_by(AgentRun.created_at, AgentRun.id)
            .limit(limit)
        )
        return list((await session.scalars(statement)).all())

    async def list_events_owned(
        self, session: AsyncSession, *, run_id: UUID, actor_id: UUID
    ) -> list[RunEvent]:
        statement = (
            select(RunEvent)
            .join(AgentRun, RunEvent.run_id == AgentRun.id)
            .where(RunEvent.run_id == run_id, AgentRun.actor_id == actor_id)
            .order_by(RunEvent.sequence)
        )
        return list((await session.scalars(statement)).all())
