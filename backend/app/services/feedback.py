"""Owner-scoped, idempotent feedback persistence for assistant messages."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, MessageFeedback


class FeedbackTargetNotFoundError(LookupError):
    """The message is absent, not assistant-authored, or not owned by the actor."""


class FeedbackService:
    async def put(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        conversation_id: UUID,
        message_id: UUID,
        rating: str,
        reason: str | None,
        comment: str | None,
    ) -> MessageFeedback:
        message = await session.scalar(
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Message.id == message_id,
                Message.conversation_id == conversation_id,
                Conversation.owner_id == owner_id,
                Message.role == "assistant",
            )
        )
        if message is None:
            raise FeedbackTargetNotFoundError

        statement = (
            insert(MessageFeedback)
            .values(
                owner_id=owner_id,
                message_id=message.id,
                run_id=message.run_id,
                rating=rating,
                reason=reason,
                comment=comment,
            )
            .on_conflict_do_update(
                constraint="uq_feedback_owner_message",
                set_={
                    "rating": rating,
                    "reason": reason,
                    "comment": comment,
                    "updated_at": func.now(),
                },
            )
            .returning(MessageFeedback)
        )
        return (await session.scalars(statement)).one()

    async def for_messages(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        message_ids: list[UUID],
    ) -> dict[UUID, MessageFeedback]:
        if not message_ids:
            return {}
        values = (
            await session.scalars(
                select(MessageFeedback).where(
                    MessageFeedback.owner_id == owner_id,
                    MessageFeedback.message_id.in_(message_ids),
                )
            )
        ).all()
        return {value.message_id: value for value in values}
