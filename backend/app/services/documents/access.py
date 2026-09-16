"""Recheck current document access before returning persisted citations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.db.models import Document, DocumentVersion, Message
from app.rag.retrieval.filters import readable_current_document

REVOKED_SOURCE_MESSAGE = "Nguồn tham khảo của câu trả lời này không còn khả dụng."


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
