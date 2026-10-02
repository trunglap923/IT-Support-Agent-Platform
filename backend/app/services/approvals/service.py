"""Owner-scoped approval drafts and one-way decisions."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRun, ApprovalRequest, ApprovalStatus, RunStatus, UserDevice
from app.services.conversations.agent_runtime_state import AgentRuntimeStateService
from app.services.conversations.run_state import RunStateService
from app.tools.schemas import CreateTicketArguments


class ApprovalNotFoundError(LookupError):
    pass


class ApprovalConflictError(RuntimeError):
    pass


class ApprovalExpiredError(RuntimeError):
    pass


class ApprovalArgumentsRejectedError(ValueError):
    pass


def canonical_argument_hash(arguments: dict[str, object]) -> tuple[dict[str, object], str]:
    serialized = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return json.loads(serialized), hashlib.sha256(serialized.encode()).hexdigest()


class ApprovalService:
    async def _expire(
        self,
        session: AsyncSession,
        *,
        approval: ApprovalRequest,
        now: datetime,
    ) -> bool:
        if approval.status != ApprovalStatus.PENDING.value:
            return False
        approval.status = ApprovalStatus.EXPIRED.value
        approval.version += 1
        run_status = await session.scalar(
            select(AgentRun.status).where(
                AgentRun.id == approval.run_id,
                AgentRun.actor_id == approval.owner_id,
            )
        )
        if run_status == RunStatus.WAITING_APPROVAL:
            await RunStateService().transition(
                session,
                run_id=approval.run_id,
                actor_id=approval.owner_id,
                target=RunStatus.CANCELLED,
                operation_id=f"approval-expired:{approval.id}",
                outcome="approval_expired",
                safe_payload={"approval_id": str(approval.id)},
                now=now,
            )
            await AgentRuntimeStateService().complete(session, run_id=approval.run_id)
        await session.flush()
        return True

    async def expire_due(
        self,
        session: AsyncSession,
        *,
        now: datetime | None = None,
        limit: int = 100,
    ) -> int:
        """Expire a bounded batch and release waiting runs in the same transaction."""

        current = now or datetime.now(UTC)
        approvals = list(
            (
                await session.scalars(
                    select(ApprovalRequest)
                    .where(
                        ApprovalRequest.status == ApprovalStatus.PENDING.value,
                        ApprovalRequest.expires_at <= current,
                    )
                    .order_by(ApprovalRequest.expires_at, ApprovalRequest.id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        expired = 0
        for approval in approvals:
            expired += int(await self._expire(session, approval=approval, now=current))
        return expired

    async def list_owned(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        status: ApprovalStatus | None = None,
        limit: int | None = None,
        before: tuple[datetime, UUID] | None = None,
    ) -> list[ApprovalRequest]:
        statement = select(ApprovalRequest).where(ApprovalRequest.owner_id == owner_id)
        if status is not None:
            statement = statement.where(ApprovalRequest.status == status.value)
        if before is not None:
            timestamp, item_id = before
            statement = statement.where(
                or_(
                    ApprovalRequest.created_at < timestamp,
                    and_(
                        ApprovalRequest.created_at == timestamp,
                        ApprovalRequest.id < item_id,
                    ),
                )
            )
        statement = statement.order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc())
        if limit is not None:
            statement = statement.limit(limit)
        return list((await session.scalars(statement)).all())

    async def create_ticket_draft(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        run_id: UUID,
        action_id: str,
        arguments: CreateTicketArguments,
        ttl: timedelta = timedelta(minutes=15),
        now: datetime | None = None,
    ) -> ApprovalRequest:
        run_exists = await session.scalar(
            select(AgentRun.id).where(AgentRun.id == run_id, AgentRun.actor_id == owner_id)
        )
        if run_exists is None:
            raise ApprovalNotFoundError("Run was not found")
        if arguments.device_id is not None:
            device_exists = await session.scalar(
                select(UserDevice.id).where(
                    UserDevice.id == arguments.device_id,
                    UserDevice.owner_id == owner_id,
                    UserDevice.active.is_(True),
                )
            )
            if device_exists is None:
                raise ApprovalArgumentsRejectedError("Device is unavailable for the approval owner")
        canonical, digest = canonical_argument_hash(arguments.model_dump(mode="json"))
        existing = await session.scalar(
            select(ApprovalRequest).where(ApprovalRequest.action_id == action_id)
        )
        if existing is not None:
            if (
                existing.owner_id == owner_id
                and existing.run_id == run_id
                and existing.arguments_hash == digest
            ):
                return existing
            raise ApprovalConflictError("Action ID is already bound to different arguments")
        created_at = now or datetime.now(UTC)
        approval = ApprovalRequest(
            action_id=action_id,
            run_id=run_id,
            owner_id=owner_id,
            tool_name="create_ticket",
            canonical_args=canonical,
            arguments_hash=digest,
            status=ApprovalStatus.PENDING.value,
            expires_at=created_at + ttl,
        )
        session.add(approval)
        await session.flush()
        return approval

    async def get_owned(
        self, session: AsyncSession, *, approval_id: UUID, owner_id: UUID
    ) -> ApprovalRequest | None:
        return cast(
            ApprovalRequest | None,
            await session.scalar(
                select(ApprovalRequest).where(
                    ApprovalRequest.id == approval_id,
                    ApprovalRequest.owner_id == owner_id,
                )
            ),
        )

    async def decide(
        self,
        session: AsyncSession,
        *,
        approval_id: UUID,
        owner_id: UUID,
        decision: Literal["approve", "reject"],
        expected_version: int,
        now: datetime | None = None,
    ) -> ApprovalRequest:
        approval = await session.scalar(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.owner_id == owner_id,
            )
            .with_for_update()
        )
        if approval is None:
            raise ApprovalNotFoundError("Approval was not found")
        current = now or datetime.now(UTC)
        if approval.status == ApprovalStatus.PENDING.value and approval.expires_at <= current:
            await self._expire(session, approval=approval, now=current)
            raise ApprovalExpiredError("Approval has expired")
        if approval.status != ApprovalStatus.PENDING.value:
            raise ApprovalConflictError("Approval has already been decided")
        if approval.version != expected_version:
            raise ApprovalConflictError("Approval version is stale")
        approval.status = (
            ApprovalStatus.APPROVED.value
            if decision == "approve"
            else ApprovalStatus.REJECTED.value
        )
        approval.decided_by = owner_id
        approval.decided_at = current
        approval.version += 1
        await session.flush()
        return approval
