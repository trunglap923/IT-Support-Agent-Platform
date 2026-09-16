"""Idempotent ticket creation from a validated approval receipt."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentRun,
    ApprovalRequest,
    ApprovalStatus,
    Ticket,
    TicketEvent,
    User,
)
from app.services.approvals.service import canonical_argument_hash
from app.tools.schemas import CreateTicketArguments


class TicketWriteRejectedError(RuntimeError):
    pass


class TicketReceiptRecoveryError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TicketCreationReceipt:
    approval_id: UUID
    ticket_id: UUID
    display_key: str
    applied: bool


class TicketWriteService:
    async def create_from_approval(
        self,
        session: AsyncSession,
        *,
        approval_id: UUID,
        owner_id: UUID,
        now: datetime | None = None,
    ) -> TicketCreationReceipt:
        approval = await session.scalar(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.owner_id == owner_id,
            )
            .with_for_update()
        )
        if approval is None:
            raise TicketWriteRejectedError("Approval was not found")
        existing = await session.scalar(select(Ticket).where(Ticket.approval_id == approval.id))
        if existing is not None:
            if approval.status != ApprovalStatus.EXECUTED.value:
                raise TicketReceiptRecoveryError("Ticket receipt status is inconsistent")
            return TicketCreationReceipt(
                approval_id=approval.id,
                ticket_id=existing.id,
                display_key=existing.display_key,
                applied=False,
            )
        if approval.status == ApprovalStatus.EXECUTED.value:
            raise TicketReceiptRecoveryError("Executed approval has no ticket receipt")
        if approval.status != ApprovalStatus.APPROVED.value:
            raise TicketWriteRejectedError("Approval is not executable")
        if approval.decided_at is None or approval.decided_at > approval.expires_at:
            raise TicketWriteRejectedError("Approval decision is outside its validity window")
        canonical, digest = canonical_argument_hash(approval.canonical_args)
        if digest != approval.arguments_hash:
            raise TicketWriteRejectedError("Approval arguments no longer match their hash")
        try:
            arguments = CreateTicketArguments.model_validate(canonical)
        except ValidationError as error:
            raise TicketWriteRejectedError("Approval arguments are invalid") from error
        row = (
            await session.execute(
                select(AgentRun, User)
                .join(User, User.id == AgentRun.actor_id)
                .where(
                    AgentRun.id == approval.run_id,
                    AgentRun.actor_id == approval.owner_id,
                    User.active.is_(True),
                )
            )
        ).one_or_none()
        if row is None:
            raise TicketWriteRejectedError("Approval owner or run is no longer valid")
        run, owner = row
        ticket = Ticket(
            display_key=f"IT-{approval.id.hex[:10].upper()}",
            owner_id=owner.id,
            department_id=owner.department_id,
            device_id=arguments.device_id,
            conversation_id=run.conversation_id,
            approval_id=approval.id,
            source="agent",
            title=arguments.title,
            description=arguments.description,
            issue_type=arguments.issue_type,
            severity=arguments.severity,
            status="open",
        )
        session.add(ticket)
        await session.flush()
        session.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_id=owner.id,
                type="ticket.created",
                safe_payload={
                    "approval_id": str(approval.id),
                    "display_key": ticket.display_key,
                },
            )
        )
        approval.status = ApprovalStatus.EXECUTED.value
        approval.executed_at = now or datetime.now(UTC)
        approval.version += 1
        await session.flush()
        return TicketCreationReceipt(
            approval_id=approval.id,
            ticket_id=ticket.id,
            display_key=ticket.display_key,
            applied=True,
        )
