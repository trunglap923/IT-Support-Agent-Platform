"""Server-owned provenance registry for semantic memory."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemorySource
from app.memory.contracts import MemorySourceReference

SOURCE_AUTHORITY: dict[str, int] = {
    "cmdb": 100,
    "idp": 100,
    "mdm": 95,
    "tool": 90,
    "ticket": 85,
    "user_confirmed": 80,
    "ai_inferred": 20,
}


class MemorySourceRegistry:
    """Resolve immutable source references without trusting caller-supplied authority."""

    async def capture(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        reference: MemorySourceReference,
        safe_excerpt: str | None = None,
        message_id: UUID | None = None,
        run_id: UUID | None = None,
        ticket_id: UUID | None = None,
        safe_metadata: Mapping[str, Any] | None = None,
    ) -> MemorySource:
        existing = await session.scalar(
            select(MemorySource).where(
                MemorySource.owner_id == owner_id,
                MemorySource.source_type == reference.source_type,
                MemorySource.source_ref == reference.source_ref,
                MemorySource.content_hash == reference.content_hash,
            )
        )
        if existing is not None:
            return existing
        source = MemorySource(
            owner_id=owner_id,
            source_type=reference.source_type,
            source_ref=reference.source_ref,
            content_hash=reference.content_hash,
            safe_excerpt=(safe_excerpt or "").strip()[:500] or None,
            authority_tier=SOURCE_AUTHORITY[reference.source_type],
            observed_at=reference.observed_at,
            message_id=message_id,
            run_id=run_id,
            ticket_id=ticket_id,
            safe_metadata=dict(safe_metadata or {}),
        )
        session.add(source)
        await session.flush()
        return source
