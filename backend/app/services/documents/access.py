"""Recheck current document access before returning persisted citations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context.builder import ContextMessage
from app.auth.principal import Principal
from app.db.models import Document, DocumentVersion, DocumentVersionStatus, Message
from app.rag.retrieval.filters import readable_current_document, readable_document_scope

REVOKED_SOURCE_MESSAGE = "Nguồn tham khảo của câu trả lời này không còn khả dụng."
HISTORICAL_SOURCE_LABEL = "[Nguồn lịch sử; cần kiểm tra hướng dẫn hiện hành]"


async def authorized_history_context(
    session: AsyncSession,
    *,
    principal: Principal,
    messages: list[Message],
    now: datetime | None = None,
) -> list[ContextMessage]:
    """Return conversation text only while every cited source remains in scope."""

    source_pairs: set[tuple[UUID, UUID]] = set()
    for message in messages:
        if message.role == "assistant" and message.outcome == "no_answer":
            # A past refusal is not evidence and can incorrectly bias a later successful search.
            continue
        for citation in message.citations:
            try:
                source_pairs.add(
                    (UUID(str(citation["document_id"])), UUID(str(citation["version_id"])))
                )
            except (KeyError, TypeError, ValueError):
                continue
    source_state: dict[tuple[UUID, UUID], str] = {}
    if source_pairs:
        current_time = now or datetime.now(UTC)
        rows = (
            await session.execute(
                select(
                    Document.id,
                    DocumentVersion.id,
                    Document.current_version_id,
                    DocumentVersion.status,
                )
                .join(DocumentVersion, DocumentVersion.document_id == Document.id)
                .where(
                    readable_document_scope(principal),
                    DocumentVersion.effective_at <= current_time,
                    or_(
                        DocumentVersion.expires_at.is_(None),
                        DocumentVersion.expires_at > current_time,
                    ),
                    DocumentVersion.status.in_(
                        [
                            DocumentVersionStatus.PUBLISHED,
                            DocumentVersionStatus.SUPERSEDED,
                        ]
                    ),
                )
            )
        ).all()
        for document_id, version_id, current_version_id, version_status in rows:
            source_state[(document_id, version_id)] = (
                "current"
                if version_id == current_version_id
                and version_status is DocumentVersionStatus.PUBLISHED
                else "historical"
            )

    context: list[ContextMessage] = []
    for message in messages:
        if message.role == "assistant" and message.outcome == "no_answer":
            continue
        content = message.content.strip()
        if not content:
            continue
        if message.citations:
            pairs: list[tuple[UUID, UUID]] = []
            malformed = False
            for citation in message.citations:
                try:
                    pairs.append(
                        (UUID(str(citation["document_id"])), UUID(str(citation["version_id"])))
                    )
                except (KeyError, TypeError, ValueError):
                    malformed = True
                    break
            if malformed or not pairs or any(pair not in source_state for pair in pairs):
                continue
            if any(source_state[pair] == "historical" for pair in pairs):
                content = f"{HISTORICAL_SOURCE_LABEL} {content}"
        if message.role == "user":
            context.append(ContextMessage(role="user", content=content))
        elif message.role == "assistant":
            context.append(ContextMessage(role="assistant", content=content))
    return context


async def redact_revoked_message_citations(
    session: AsyncSession,
    *,
    principal: Principal,
    messages: list[Message],
    now: datetime | None = None,
) -> dict[UUID, tuple[str, str | None, list[dict[str, object]]]]:
    source_pairs: set[tuple[UUID, UUID]] = set()
    for message in messages:
        for citation in message.citations:
            try:
                source_pairs.add(
                    (UUID(str(citation["document_id"])), UUID(str(citation["version_id"])))
                )
            except (KeyError, TypeError, ValueError):
                continue
    if not source_pairs:
        return {}

    allowed = set(
        (
            await session.execute(
                select(Document.id, DocumentVersion.id)
                .join(DocumentVersion, DocumentVersion.document_id == Document.id)
                .where(readable_current_document(principal, now=now or datetime.now(UTC)))
            )
        ).all()
    )
    redactions: dict[UUID, tuple[str, str | None, list[dict[str, object]]]] = {}
    for message in messages:
        if not message.citations:
            continue
        valid: list[dict[str, object]] = []
        for citation in message.citations:
            try:
                pair = (
                    UUID(str(citation["document_id"])),
                    UUID(str(citation["version_id"])),
                )
            except (KeyError, TypeError, ValueError):
                continue
            if pair in allowed:
                valid.append(citation)
        if len(valid) != len(message.citations):
            redactions[message.id] = (REVOKED_SOURCE_MESSAGE, "source_revoked", [])
    return redactions
