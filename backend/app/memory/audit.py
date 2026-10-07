"""Owner explanations and reviewer workflow for semantic memory conflicts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    IncidentEpisode,
    MemoryAssertion,
    MemoryConflict,
    MemoryDecision,
    MemoryFact,
    MemorySource,
)
from app.memory.lifecycle import MemoryConflictError, MemoryNotFoundError


class MemoryAuditService:
    async def explain_fact(
        self, session: AsyncSession, *, owner_id: UUID, fact_id: UUID
    ) -> tuple[MemoryAssertion, MemorySource, list[MemoryDecision]]:
        fact = await session.scalar(
            select(MemoryFact).where(MemoryFact.id == fact_id, MemoryFact.owner_id == owner_id)
        )
        if fact is None:
            raise MemoryNotFoundError("Memory fact not found")
        assertion = await session.scalar(
            select(MemoryAssertion)
            .where(
                MemoryAssertion.compatibility_fact_id == fact_id,
                MemoryAssertion.owner_id == owner_id,
            )
            .order_by(MemoryAssertion.created_at.desc())
        )
        if assertion is None:
            raise MemoryNotFoundError("Memory assertion not found")
        source = await session.get(MemorySource, assertion.source_id)
        if source is None or source.owner_id != owner_id:
            raise MemoryNotFoundError("Memory source not found")
        decisions = list(
            await session.scalars(
                select(MemoryDecision)
                .where(
                    MemoryDecision.owner_id == owner_id,
                    (MemoryDecision.target_assertion_id == assertion.id)
                    | (MemoryDecision.resulting_assertion_id == assertion.id),
                )
                .order_by(MemoryDecision.created_at)
            )
        )
        return assertion, source, decisions

    async def list_episodes(
        self, session: AsyncSession, *, owner_id: UUID, limit: int = 20
    ) -> list[IncidentEpisode]:
        return list(
            await session.scalars(
                select(IncidentEpisode)
                .where(
                    IncidentEpisode.owner_id == owner_id,
                    IncidentEpisode.deleted_at.is_(None),
                )
                .order_by(IncidentEpisode.completed_at.desc(), IncidentEpisode.id.desc())
                .limit(limit)
            )
        )

    async def list_conflicts(
        self, session: AsyncSession, *, status: str, limit: int = 100
    ) -> list[MemoryConflict]:
        return list(
            await session.scalars(
                select(MemoryConflict)
                .where(MemoryConflict.status == status)
                .order_by(MemoryConflict.created_at, MemoryConflict.id)
                .limit(limit)
            )
        )

    async def resolve_conflict(
        self,
        session: AsyncSession,
        *,
        conflict_id: UUID,
        selected_assertion_id: UUID,
        reviewer_id: UUID,
    ) -> MemoryConflict:
        conflict = await session.scalar(
            select(MemoryConflict).where(MemoryConflict.id == conflict_id).with_for_update()
        )
        if conflict is None:
            raise MemoryNotFoundError("Memory conflict not found")
        if conflict.status == "resolved":
            if conflict.selected_assertion_id != selected_assertion_id:
                raise MemoryConflictError("Memory conflict was already resolved differently")
            return conflict
        allowed = {conflict.assertion_a_id, conflict.assertion_b_id}
        if selected_assertion_id not in allowed:
            raise MemoryConflictError("Selected assertion does not belong to this conflict")
        assertions = list(
            await session.scalars(
                select(MemoryAssertion).where(MemoryAssertion.id.in_(allowed)).with_for_update()
            )
        )
        selected = next(item for item in assertions if item.id == selected_assertion_id)
        rejected = next(item for item in assertions if item.id != selected_assertion_id)
        if rejected.status == "active":
            rejected.status = "superseded"
            rejected.valid_to = datetime.now(UTC)
            rejected.version += 1
            await session.flush()
        selected.status = "active"
        selected.valid_to = None
        selected.deleted_at = None
        selected.version += 1
        conflict.status = "resolved"
        conflict.resolution = "reviewer_selected"
        conflict.selected_assertion_id = selected.id
        conflict.reviewed_by = reviewer_id
        conflict.reviewed_at = datetime.now(UTC)
        await session.flush()
        return conflict
