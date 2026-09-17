"""Bounded maintenance operations executed by the background queue."""

from __future__ import annotations

from datetime import datetime

from app.db import Database
from app.services.approvals import ApprovalService


async def expire_pending_approvals(
    database: Database,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> int:
    async with database.session() as session, session.begin():
        return await ApprovalService().expire_due(session, now=now, limit=limit)
