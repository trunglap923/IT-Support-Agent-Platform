"""Database lifecycle for consent records and unconfirmed memory candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Conversation,
    MemoryCandidate,
    MemoryConsentEvent,
    MemoryExtractionJob,
    Message,
    User,
)
from app.memory.extractor import extract_candidate_proposals


class MemoryConflictError(RuntimeError):
    """The caller used stale state or a source it does not own."""


@dataclass(frozen=True, slots=True)
class ConsentState:
    enabled: bool
    epoch: int


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    job: MemoryExtractionJob
    candidates: tuple[MemoryCandidate, ...]
    created: bool


class MemoryLifecycleService:
    async def get_consent(self, session: AsyncSession, *, owner_id: UUID) -> ConsentState:
        value = await session.execute(
            select(User.memory_enabled, User.memory_epoch).where(User.id == owner_id)
        )
        row = value.one_or_none()
        if row is None:
            raise LookupError("User not found")
        return ConsentState(enabled=row.memory_enabled, epoch=row.memory_epoch)

    async def set_consent(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        enabled: bool,
        expected_epoch: int,
    ) -> ConsentState:
        user = await session.scalar(select(User).where(User.id == owner_id).with_for_update())
        if user is None:
            raise LookupError("User not found")
        if user.memory_epoch != expected_epoch:
            raise MemoryConflictError("Memory settings changed; refresh and retry")
        if user.memory_enabled == enabled:
            return ConsentState(enabled=enabled, epoch=user.memory_epoch)
        user.memory_enabled = enabled
        user.memory_epoch += 1
        session.add(MemoryConsentEvent(owner_id=owner_id, enabled=enabled, epoch=user.memory_epoch))
        await session.flush()
        return ConsentState(enabled=enabled, epoch=user.memory_epoch)

    async def extract_from_message(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        source_message_id: UUID,
        now: datetime | None = None,
    ) -> ExtractionResult | None:
        existing = await session.scalar(
            select(MemoryExtractionJob).where(
                MemoryExtractionJob.source_message_id == source_message_id
            )
        )
        if existing is not None:
            candidates = tuple(
                await session.scalars(
                    select(MemoryCandidate)
                    .where(MemoryCandidate.job_id == existing.id)
                    .order_by(MemoryCandidate.created_at, MemoryCandidate.id)
                )
            )
            return ExtractionResult(job=existing, candidates=candidates, created=False)

        user = await session.scalar(select(User).where(User.id == owner_id).with_for_update())
        if user is None:
            raise LookupError("User not found")
        if not user.memory_enabled:
            return None
        source = (
            await session.execute(
                select(Message, Conversation.owner_id)
                .join(Conversation, Conversation.id == Message.conversation_id)
                .where(Message.id == source_message_id)
            )
        ).one_or_none()
        if source is None:
            raise MemoryConflictError("Memory source must be an owned user message")
        message, message_owner_id = source
        if message_owner_id != owner_id or message.role != "user":
            raise MemoryConflictError("Memory source must be an owned user message")

        current_time = now or datetime.now(UTC)
        job = MemoryExtractionJob(
            owner_id=owner_id,
            run_id=message.run_id,
            source_message_id=message.id,
            captured_epoch=user.memory_epoch,
            status="completed",
            completed_at=current_time,
        )
        session.add(job)
        await session.flush()
        candidates = tuple(
            MemoryCandidate(
                job_id=job.id,
                owner_id=owner_id,
                source_conversation_id=message.conversation_id,
                kind=proposal.kind,
                key=proposal.key,
                value=proposal.value,
                evidence=proposal.evidence,
                expires_at=current_time + timedelta(days=7),
            )
            for proposal in extract_candidate_proposals(message.content)
        )
        session.add_all(candidates)
        await session.flush()
        return ExtractionResult(job=job, candidates=candidates, created=True)

    async def list_pending_candidates(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        now: datetime | None = None,
    ) -> list[MemoryCandidate]:
        current_time = now or datetime.now(UTC)
        return list(
            await session.scalars(
                select(MemoryCandidate)
                .where(
                    MemoryCandidate.owner_id == owner_id,
                    MemoryCandidate.status == "pending",
                    MemoryCandidate.expires_at > current_time,
                )
                .order_by(MemoryCandidate.created_at, MemoryCandidate.id)
            )
        )
