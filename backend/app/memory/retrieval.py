"""Retrieve confirmed memory as bounded, server-labelled agent context."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context.builder import ContextMessage
from app.db.models import MemoryFact, User


class MemoryContextService:
    async def context_messages(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        device_id: UUID | None,
        now: datetime | None = None,
        limit: int = 5,
    ) -> list[ContextMessage]:
        current_time = now or datetime.now(UTC)
        consent = await session.execute(select(User.memory_enabled).where(User.id == owner_id))
        if consent.scalar_one_or_none() is not True:
            return []
        scope_filter = MemoryFact.scope == "global"
        if device_id is not None:
            scope_filter = or_(
                scope_filter,
                and_(MemoryFact.scope == "device", MemoryFact.device_id == device_id),
            )
        values = list(
            await session.scalars(
                select(MemoryFact)
                .where(
                    MemoryFact.owner_id == owner_id,
                    MemoryFact.deleted_at.is_(None),
                    MemoryFact.expires_at > current_time,
                    scope_filter,
                )
                .order_by(MemoryFact.updated_at.desc(), MemoryFact.id)
                .limit(limit)
            )
        )
        return [
            ContextMessage(
                role="memory",
                content=f"Confirmed user data: {value.key}={value.value}",
            )
            for value in values
        ]
