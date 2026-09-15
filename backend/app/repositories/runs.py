"""Owner-scoped run and event queries."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRun, RunEvent


class RunRepository:
    async def get_owned(
        self, session: AsyncSession, *, run_id: UUID, actor_id: UUID
    ) -> AgentRun | None:
        statement = select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.actor_id == actor_id,
        )
        return cast(AgentRun | None, await session.scalar(statement))

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
