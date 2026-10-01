"""Resume an approval checkpoint while preserving database run ownership."""

from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import select

from app.agent.approval_checkpoint import resume_ticket_approval
from app.db import Database
from app.db.models import ApprovalRequest, ApprovalStatus, Message, RunStatus
from app.repositories.conversations import ConversationRepository
from app.repositories.runs import RunRepository
from app.services.conversations.run_state import RunStateService
from app.services.tickets import TicketWriteService


async def execute_approval_resume_run(
    database: Database, *, run_id: UUID, worker_id: str | None = None
) -> str:
    repository = RunRepository()
    state = RunStateService(repository)
    async with database.session() as session, session.begin():
        run = await repository.get_for_update(session, run_id=run_id)
        if run is None:
            return "missing"
        resumable = run.status is RunStatus.RESUME_QUEUED or (
            run.status is RunStatus.RUNNING
            and worker_id is not None
            and run.lease_owner == worker_id
        )
        if not resumable:
            return "duplicate"
        if worker_id is not None and run.lease_owner != worker_id:
            return "lease_lost"
        approval = await session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.run_id == run.id,
                ApprovalRequest.owner_id == run.actor_id,
                ApprovalRequest.status.in_(
                    [
                        ApprovalStatus.APPROVED.value,
                        ApprovalStatus.REJECTED.value,
                        ApprovalStatus.EXECUTED.value,
                    ]
                ),
            )
        )
        if approval is None:
            return "not_approval"
        actor_id = run.actor_id
        checkpoint_thread_id = run.checkpoint_thread_id
        if run.status is RunStatus.RESUME_QUEUED:
            await state.transition(
                session,
                run_id=run.id,
                actor_id=actor_id,
                target=RunStatus.RUNNING,
                operation_id=f"approval-resume-claim:{approval.id}",
            )

    async_url = database.engine.url.render_as_string(hide_password=False)
    await asyncio.to_thread(
        resume_ticket_approval,
        database_url=async_url,
        checkpoint_thread_id=checkpoint_thread_id,
        run_id=run_id,
        actor_id=actor_id,
        approval_id=approval.id,
        arguments_hash=approval.arguments_hash,
        approved=approval.status in {ApprovalStatus.APPROVED.value, ApprovalStatus.EXECUTED.value},
    )
    async with database.session() as session, session.begin():
        ticket_receipt = None
        if approval.status in {
            ApprovalStatus.APPROVED.value,
            ApprovalStatus.EXECUTED.value,
        }:
            ticket_receipt = await TicketWriteService().create_from_approval(
                session,
                approval_id=approval.id,
                owner_id=actor_id,
            )
        final_outcome = "ticket_created" if ticket_receipt is not None else "approval_rejected"
        existing_message = await session.scalar(
            select(Message.id).where(
                Message.run_id == run_id,
                Message.outcome == final_outcome,
            )
        )
        if existing_message is None:
            await ConversationRepository().touch(session, conversation_id=run.conversation_id)
            session.add(
                Message(
                    conversation_id=run.conversation_id,
                    run_id=run.id,
                    role="assistant",
                    content=(
                        f"Ticket {ticket_receipt.display_key} đã được tạo."
                        if ticket_receipt is not None
                        else "Bạn đã từ chối bản nháp; hệ thống không tạo ticket."
                    ),
                    outcome=final_outcome,
                    citations=[],
                )
            )
        await state.transition(
            session,
            run_id=run_id,
            actor_id=actor_id,
            target=RunStatus.COMPLETED,
            operation_id=f"approval-resume-complete:{approval.id}",
            outcome=final_outcome,
            safe_payload={
                "approval_id": str(approval.id),
                "ticket_id": str(ticket_receipt.ticket_id) if ticket_receipt is not None else None,
            },
        )
    return "resumed"
