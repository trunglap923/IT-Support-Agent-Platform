"""User identity queries; callers own transaction boundaries."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models import User


def normalize_email(email: str) -> str:
    return email.strip().lower()


class UserRepository:
    async def get_by_id(self, session: AsyncSession, user_id: UUID) -> User | None:
        statement = select(User).where(User.id == user_id).options(joinedload(User.department))
        return cast(User | None, await session.scalar(statement))

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        statement = (
            select(User)
            .where(User.email == normalize_email(email))
            .options(joinedload(User.department))
        )
        return cast(User | None, await session.scalar(statement))

    def add(self, session: AsyncSession, user: User) -> None:
        session.add(user)
