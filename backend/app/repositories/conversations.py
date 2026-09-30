"""Owner-scoped conversation and message queries."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message


class ConversationRepository:
    async def create(self, session: AsyncSession, *, owner_id: UUID, title: str) -> Conversation:
        conversation = Conversation(owner_id=owner_id, title=title, issue_state={})
        session.add(conversation)
        await session.flush()
        return conversation

    async def get_owned(
        self, session: AsyncSession, *, conversation_id: UUID, owner_id: UUID
    ) -> Conversation | None:
        statement = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.owner_id == owner_id,
        )
        return cast(Conversation | None, await session.scalar(statement))

    async def list_owned(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        limit: int | None = None,
        before: tuple[datetime, UUID] | None = None,
    ) -> list[Conversation]:
        statement = (
            select(Conversation)
            .where(Conversation.owner_id == owner_id)
            .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        )
        if before is not None:
            timestamp, item_id = before
            statement = statement.where(
                or_(
                    Conversation.created_at < timestamp,
                    and_(Conversation.created_at == timestamp, Conversation.id < item_id),
                )
            )
        if limit is not None:
            statement = statement.limit(limit)
        return list((await session.scalars(statement)).all())

    async def list_messages_owned(
        self,
        session: AsyncSession,
        *,
        conversation_id: UUID,
        owner_id: UUID,
        limit: int | None = None,
        before: tuple[datetime, UUID] | None = None,
    ) -> list[Message]:
        statement = (
            select(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Message.conversation_id == conversation_id,
                Conversation.owner_id == owner_id,
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
        )
        if before is not None:
            timestamp, item_id = before
            statement = statement.where(
                or_(
                    Message.created_at < timestamp,
                    and_(Message.created_at == timestamp, Message.id < item_id),
                )
            )
        if limit is not None:
            statement = statement.limit(limit)
        return list((await session.scalars(statement)).all())
