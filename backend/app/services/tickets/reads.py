"""Ticket reads with owner, department and role scope applied in SQL."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.db.models import Ticket, TicketStatus, UserRole


class TicketReadService:
    async def list_owned(
        self, session: AsyncSession, *, principal: Principal, limit: int = 100
    ) -> list[Ticket]:
        statement = (
            select(Ticket)
            .where(Ticket.owner_id == principal.user_id)
            .order_by(Ticket.updated_at.desc(), Ticket.id.desc())
            .limit(min(max(limit, 1), 100))
        )
        return list((await session.scalars(statement)).all())

    async def list_my_open(
        self, session: AsyncSession, *, principal: Principal, limit: int = 10
    ) -> list[Ticket]:
        statement = (
            select(Ticket)
            .where(
                Ticket.owner_id == principal.user_id,
                Ticket.status.in_([TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value]),
            )
            .order_by(Ticket.created_at.desc(), Ticket.id.desc())
            .limit(min(max(limit, 1), 10))
        )
        return list((await session.scalars(statement)).all())

    async def list_visible(
        self,
        session: AsyncSession,
        *,
        principal: Principal,
        status: TicketStatus | None = None,
        limit: int = 100,
    ) -> list[Ticket]:
        statement = select(Ticket)
        if principal.role is UserRole.EMPLOYEE:
            statement = statement.where(Ticket.owner_id == principal.user_id)
        elif principal.role is UserRole.IT:
            statement = statement.where(Ticket.department_id == principal.department_id)
        if status is not None:
            statement = statement.where(Ticket.status == status.value)
        statement = statement.order_by(Ticket.updated_at.desc(), Ticket.id.desc()).limit(
            min(max(limit, 1), 100)
        )
        return list((await session.scalars(statement)).all())

    async def get_visible(
        self, session: AsyncSession, *, principal: Principal, ticket_id: UUID
    ) -> Ticket | None:
        statement = select(Ticket).where(Ticket.id == ticket_id)
        if principal.role is UserRole.EMPLOYEE:
            statement = statement.where(Ticket.owner_id == principal.user_id)
        elif principal.role is UserRole.IT:
            statement = statement.where(Ticket.department_id == principal.department_id)
        return cast(Ticket | None, await session.scalar(statement))
