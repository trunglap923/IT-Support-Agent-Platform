"""Atomic user cancellation for runs and their pending approval drafts."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.working_memory.service import WorkingMemoryService
from app.db.models import ApprovalRequest, ApprovalStatus, RunStatus
from app.services.conversations.agent_runtime_state import AgentRuntimeStateService
from app.services.conversations.run_state import RunStateService, TransitionResult


class RunCancellationService:
    """Cancel a run while closing any approval that can no longer be acted on."""

    async def cancel_owned(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        actor_id: UUID,
        expected_version: int,
        reason: Literal["user_requested", "draft_replaced"] = "user_requested",
    ) -> TransitionResult:
        # Approval decisions lock approval then run. Keep the same lock order here
        # so a cancel racing with approve/reject cannot deadlock or leave a draft
        # actionable after its run is terminal.
        pending_approvals = list(
            (
                await session.scalars(
                    select(ApprovalRequest)
                    .where(
                        ApprovalRequest.run_id == run_id,
                        ApprovalRequest.owner_id == actor_id,
                        ApprovalRequest.status == ApprovalStatus.PENDING.value,
                    )
                    .order_by(ApprovalRequest.id)
                    .with_for_update()
                )
            ).all()
        )
        transition = await RunStateService().transition(
            session,
            run_id=run_id,
            actor_id=actor_id,
            target=RunStatus.CANCELLED,
            operation_id=f"user-cancel:{run_id}",
            outcome=("draft_replaced" if reason == "draft_replaced" else "cancelled_by_user"),
            safe_payload={"reason": reason},
            expected_version=expected_version,
        )
        if transition.applied:
            for approval in pending_approvals:
                approval.status = ApprovalStatus.EXPIRED.value
                approval.version += 1
            await AgentRuntimeStateService().complete(session, run_id=run_id)
            working_memory = WorkingMemoryService()
            snapshot = await working_memory.load(
                session,
                run_id=run_id,
                owner_id=actor_id,
            )
            if snapshot is not None:
                await working_memory.apply_transition(
                    session,
                    run_id=run_id,
                    owner_id=actor_id,
                    target="cancelled",
                    operation_id=f"working-memory-cancel:{run_id}",
                    safe_payload={"reason": reason},
                )
            await session.flush()
        return transition
