"""Owner-scoped approval drafts and one-way decisions."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentRun, ApprovalRequest, ApprovalStatus
from app.tools.schemas import CreateTicketArguments


class ApprovalNotFoundError(LookupError):
    pass


class ApprovalConflictError(RuntimeError):
    pass


class ApprovalExpiredError(RuntimeError):
    pass


def canonical_argument_hash(arguments: dict[str, object]) -> tuple[dict[str, object], str]:
    serialized = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return json.loads(serialized), hashlib.sha256(serialized.encode()).hexdigest()


class ApprovalService:
    async def list_owned(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        status: ApprovalStatus | None = None,
    ) -> list[ApprovalRequest]:
        statement = select(ApprovalRequest).where(ApprovalRequest.owner_id == owner_id)
        if status is not None:
            statement = statement.where(ApprovalRequest.status == status.value)
        statement = statement.order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc())
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
            approval.status = ApprovalStatus.EXPIRED.value
            approval.version += 1
            await session.flush()
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
