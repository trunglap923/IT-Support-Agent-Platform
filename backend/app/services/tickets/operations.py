"""Role-scoped ticket workflow transitions for IT operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.db.models import Ticket, TicketEvent, TicketStatus, UserRole


class TicketOperationNotFoundError(LookupError):
    pass


class TicketOperationConflictError(RuntimeError):
    pass


TicketAction = Literal["start", "resolve", "reopen"]


@dataclass(frozen=True, slots=True)
class TicketTransition:
    action: TicketAction
    source: TicketStatus
    target: TicketStatus


TRANSITIONS: dict[TicketAction, TicketTransition] = {
    "start": TicketTransition("start", TicketStatus.OPEN, TicketStatus.IN_PROGRESS),
    "resolve": TicketTransition("resolve", TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED),
    "reopen": TicketTransition("reopen", TicketStatus.RESOLVED, TicketStatus.OPEN),
}


class TicketOperationService:
    async def transition(
        self,
        session: AsyncSession,
        *,
        principal: Principal,
        ticket_id: UUID,
        action: TicketAction,
        expected_version: int,
        resolution_note: str | None = None,
    ) -> Ticket:
        statement = select(Ticket).where(Ticket.id == ticket_id).with_for_update()
        if principal.role is UserRole.IT:
            statement = statement.where(Ticket.department_id == principal.department_id)
        ticket = await session.scalar(statement)
        if ticket is None:
            raise TicketOperationNotFoundError("Ticket was not found")
        transition = TRANSITIONS[action]
        if ticket.version != expected_version:
            raise TicketOperationConflictError("Ticket version is stale")
        if ticket.status != transition.source.value:
            raise TicketOperationConflictError(
                f"Cannot {action} a ticket in {ticket.status} status"
            )
        normalized_note = resolution_note.strip() if resolution_note else None
        if action == "resolve" and not normalized_note:
            raise TicketOperationConflictError("Resolution note is required")
        ticket.status = transition.target.value
        ticket.resolution_note = normalized_note if action == "resolve" else None
        ticket.version += 1
        session.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=principal.user_id,
                type=f"ticket.{transition.target.value}",
                safe_payload={"resolution_note": normalized_note} if normalized_note else {},
            )
        )
        await session.flush()
        return ticket
