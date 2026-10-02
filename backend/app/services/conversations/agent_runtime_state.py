"""Persistence for resumable agent runtime snapshots."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRuntimeState


class AgentRuntimeStateService:
    async def get(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        for_update: bool = False,
    ) -> AgentRuntimeState | None:
        statement = select(AgentRuntimeState).where(AgentRuntimeState.run_id == run_id)
        if for_update:
            statement = statement.with_for_update()
        return cast(AgentRuntimeState | None, await session.scalar(statement))

    async def pause(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        serialized_state: str,
        approval_call_id: str,
    ) -> AgentRuntimeState:
        item = await self.get(session, run_id=run_id, for_update=True)
        if item is None:
            item = AgentRuntimeState(
                run_id=run_id,
                runtime="openai_agents",
                serialized_state=serialized_state,
                approval_call_id=approval_call_id,
                status="paused",
            )
            session.add(item)
        else:
            item.serialized_state = serialized_state
            item.approval_call_id = approval_call_id
            item.status = "paused"
            item.version += 1
        await session.flush()
        return item

    async def activate(self, session: AsyncSession, *, run_id: UUID) -> AgentRuntimeState | None:
        item = await self.get(session, run_id=run_id, for_update=True)
        if item is None:
            return None
        item.status = "active"
        item.version += 1
        await session.flush()
        return item

    async def complete(self, session: AsyncSession, *, run_id: UUID) -> None:
        item = await self.get(session, run_id=run_id, for_update=True)
        if item is None:
            return
        item.serialized_state = None
        item.approval_call_id = None
        item.status = "completed"
        item.version += 1
        await session.flush()
