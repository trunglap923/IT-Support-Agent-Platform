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
    MemoryFact,
    Message,
    User,
    UserDevice,
)
from app.memory.extractor import extract_candidate_proposals


class MemoryConflictError(RuntimeError):
    """The caller used stale state or a source it does not own."""


class MemoryNotFoundError(LookupError):
    """An owner-scoped memory resource was not found."""


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
    async def create_device(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        label: str,
        platform: str,
    ) -> UserDevice:
        device = UserDevice(
            owner_id=owner_id,
            label=" ".join(label.strip().split()),
            platform=platform,
        )
        session.add(device)
        await session.flush()
        return device

    async def list_devices(self, session: AsyncSession, *, owner_id: UUID) -> list[UserDevice]:
        return list(
            await session.scalars(
                select(UserDevice)
                .where(UserDevice.owner_id == owner_id, UserDevice.active.is_(True))
                .order_by(UserDevice.label, UserDevice.id)
            )
        )

    async def assign_conversation_device(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        conversation_id: UUID,
        device_id: UUID | None,
    ) -> Conversation:
        conversation = await session.scalar(
            select(Conversation)
            .where(Conversation.id == conversation_id, Conversation.owner_id == owner_id)
            .with_for_update()
        )
        if conversation is None:
            raise MemoryNotFoundError("Conversation not found")
        if device_id is not None:
            device = await session.scalar(
                select(UserDevice).where(
                    UserDevice.id == device_id,
                    UserDevice.owner_id == owner_id,
                    UserDevice.active.is_(True),
                )
            )
            if device is None:
                raise MemoryNotFoundError("Device not found")
        conversation.device_id = device_id
        conversation.version += 1
        await session.flush()
        return conversation

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

    async def confirm_candidate(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        candidate_id: UUID,
        expected_version: int,
        device_id: UUID | None,
        corrected_value: str | None = None,
        now: datetime | None = None,
    ) -> MemoryFact:
        current_time = now or datetime.now(UTC)
        user = await session.scalar(select(User).where(User.id == owner_id).with_for_update())
        candidate = await session.scalar(
            select(MemoryCandidate)
            .where(MemoryCandidate.id == candidate_id, MemoryCandidate.owner_id == owner_id)
            .with_for_update()
        )
        if user is None or candidate is None:
            raise MemoryNotFoundError("Memory candidate not found")
        if candidate.status != "pending" or candidate.version != expected_version:
            raise MemoryConflictError("Memory candidate changed; refresh and retry")
        if candidate.expires_at <= current_time:
            candidate.status = "expired"
            candidate.version += 1
            candidate.decided_at = current_time
            raise MemoryConflictError("Memory candidate expired")
        job = await session.get(MemoryExtractionJob, candidate.job_id)
        if job is None or not user.memory_enabled or job.captured_epoch != user.memory_epoch:
            raise MemoryConflictError("Memory consent changed after extraction")
        scope = "device" if candidate.kind == "device" else "global"
        if (scope == "device") != (device_id is not None):
            raise MemoryConflictError("Device memory requires an owned device")
        if device_id is not None:
            owned_device = await session.scalar(
                select(UserDevice).where(
                    UserDevice.id == device_id,
                    UserDevice.owner_id == owner_id,
                    UserDevice.active.is_(True),
                )
            )
            if owned_device is None:
                raise MemoryNotFoundError("Device not found")

        value = " ".join((corrected_value or candidate.value).strip().split())
        if not value or len(value) > 240:
            raise MemoryConflictError("Memory value must contain 1 to 240 characters")
        device_filter = (
            MemoryFact.device_id.is_(None)
            if device_id is None
            else MemoryFact.device_id == device_id
        )
        existing = await session.scalar(
            select(MemoryFact)
            .where(
                MemoryFact.owner_id == owner_id,
                MemoryFact.scope == scope,
                device_filter,
                MemoryFact.kind == candidate.kind,
                MemoryFact.key == candidate.key,
                MemoryFact.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if existing is not None:
            existing.deleted_at = current_time
            existing.version += 1
            await session.flush()
        candidate.status = "confirmed"
        candidate.device_id = device_id
        candidate.value = value
        candidate.version += 1
        candidate.decided_at = current_time
        fact = MemoryFact(
            owner_id=owner_id,
            candidate_id=candidate.id,
            source_conversation_id=candidate.source_conversation_id,
            kind=candidate.kind,
            key=candidate.key,
            value=value,
            scope=scope,
            device_id=device_id,
            expires_at=current_time + timedelta(days=90),
        )
        session.add(fact)
        await session.flush()
        return fact

    async def reject_candidate(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        candidate_id: UUID,
        expected_version: int,
        now: datetime | None = None,
    ) -> MemoryCandidate:
        candidate = await session.scalar(
            select(MemoryCandidate)
            .where(MemoryCandidate.id == candidate_id, MemoryCandidate.owner_id == owner_id)
            .with_for_update()
        )
        if candidate is None:
            raise MemoryNotFoundError("Memory candidate not found")
        if candidate.status != "pending" or candidate.version != expected_version:
            raise MemoryConflictError("Memory candidate changed; refresh and retry")
        candidate.status = "rejected"
        candidate.version += 1
        candidate.decided_at = now or datetime.now(UTC)
        await session.flush()
        return candidate

    async def list_facts(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        now: datetime | None = None,
    ) -> list[MemoryFact]:
        current_time = now or datetime.now(UTC)
        return list(
            await session.scalars(
                select(MemoryFact)
                .where(
                    MemoryFact.owner_id == owner_id,
                    MemoryFact.deleted_at.is_(None),
                    MemoryFact.expires_at > current_time,
                )
                .order_by(MemoryFact.updated_at.desc(), MemoryFact.id)
            )
        )
