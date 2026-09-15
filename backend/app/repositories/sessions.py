"""Opaque session persistence queries."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import AuthSession, User


class SessionRepository:
    def add(self, session: AsyncSession, auth_session: AuthSession) -> None:
        session.add(auth_session)

    async def get_active_by_token_hash(
        self,
        session: AsyncSession,
        *,
        token_hash: str,
        now: datetime,
    ) -> AuthSession | None:
        statement = (
            select(AuthSession)
            .join(AuthSession.user)
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
                User.active.is_(True),
            )
            .options(joinedload(AuthSession.user).joinedload(User.department))
        )
        return cast(AuthSession | None, await session.scalar(statement))

    async def revoke(
        self,
        session: AsyncSession,
        *,
        session_id: UUID,
        revoked_at: datetime,
    ) -> None:
        await session.execute(
            update(AuthSession)
            .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
