"""Ticket reads with owner, department and role scope applied in SQL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.auth.principal import Principal
from app.db.models import Ticket, TicketIssueType, TicketSeverity, TicketStatus, UserRole


@dataclass(frozen=True, slots=True)
class TicketSummary:
    total: int
    open: int
    in_progress: int
    resolved: int
    high_unresolved: int


class TicketReadService:
    async def summarize_owned(
        self,
        session: AsyncSession,
        *,
        principal: Principal,
    ) -> TicketSummary:
        return await self._summarize(
            session,
            scope=Ticket.owner_id == principal.user_id,
        )

    async def summarize_visible(
        self,
        session: AsyncSession,
        *,
        principal: Principal,
    ) -> TicketSummary:
        scope = None
        if principal.role is UserRole.EMPLOYEE:
            scope = Ticket.owner_id == principal.user_id
        elif principal.role is UserRole.IT:
            scope = Ticket.department_id == principal.department_id
        return await self._summarize(session, scope=scope)

    async def _summarize(
        self,
        session: AsyncSession,
        *,
        scope: ColumnElement[bool] | None,
    ) -> TicketSummary:
        statement = select(
            func.count(Ticket.id),
            func.count(Ticket.id).filter(Ticket.status == TicketStatus.OPEN.value),
            func.count(Ticket.id).filter(Ticket.status == TicketStatus.IN_PROGRESS.value),
            func.count(Ticket.id).filter(Ticket.status == TicketStatus.RESOLVED.value),
            func.count(Ticket.id).filter(
                Ticket.severity == TicketSeverity.HIGH.value,
                Ticket.status != TicketStatus.RESOLVED.value,
            ),
        )
        if scope is not None:
            statement = statement.where(scope)
        row = (await session.execute(statement)).one()
        return TicketSummary(
            total=int(row[0]),
            open=int(row[1]),
            in_progress=int(row[2]),
            resolved=int(row[3]),
            high_unresolved=int(row[4]),
        )

    async def list_owned(
        self,
        session: AsyncSession,
        *,
        principal: Principal,
        limit: int = 100,
        before: tuple[datetime, UUID] | None = None,
        status: TicketStatus | None = None,
        issue_type: TicketIssueType | None = None,
        severity: TicketSeverity | None = None,
    ) -> list[Ticket]:
        statement = select(Ticket).where(Ticket.owner_id == principal.user_id)
        if status is not None:
            statement = statement.where(Ticket.status == status.value)
        if issue_type is not None:
            statement = statement.where(Ticket.issue_type == issue_type.value)
        if severity is not None:
            statement = statement.where(Ticket.severity == severity.value)
        if before is not None:
            timestamp, item_id = before
            statement = statement.where(
                or_(
                    Ticket.updated_at < timestamp,
                    and_(Ticket.updated_at == timestamp, Ticket.id < item_id),
                )
            )
        statement = statement.order_by(Ticket.updated_at.desc(), Ticket.id.desc()).limit(
            min(max(limit, 1), 101)
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

    async def list_my_recent(
        self, session: AsyncSession, *, principal: Principal, limit: int = 10
    ) -> list[Ticket]:
        """Return recent tickets owned by the actor, including terminal states."""

        statement = (
            select(Ticket)
            .where(Ticket.owner_id == principal.user_id)
            .order_by(Ticket.updated_at.desc(), Ticket.id.desc())
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
        before: tuple[datetime, UUID] | None = None,
        issue_type: TicketIssueType | None = None,
        severity: TicketSeverity | None = None,
    ) -> list[Ticket]:
        statement = select(Ticket)
        if principal.role is UserRole.EMPLOYEE:
            statement = statement.where(Ticket.owner_id == principal.user_id)
        elif principal.role is UserRole.IT:
            statement = statement.where(Ticket.department_id == principal.department_id)
        if status is not None:
            statement = statement.where(Ticket.status == status.value)
        if issue_type is not None:
            statement = statement.where(Ticket.issue_type == issue_type.value)
        if severity is not None:
            statement = statement.where(Ticket.severity == severity.value)
        if before is not None:
            timestamp, item_id = before
            statement = statement.where(
                or_(
                    Ticket.updated_at < timestamp,
                    and_(Ticket.updated_at == timestamp, Ticket.id < item_id),
                )
            )
        statement = statement.order_by(Ticket.updated_at.desc(), Ticket.id.desc()).limit(
            min(max(limit, 1), 101)
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
