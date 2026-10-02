"""Centralized, owner-scoped context selection for agent runtimes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context.schemas import DeviceContext, SupportContext
from app.auth.principal import Principal
from app.db.models import Conversation, Message, UserDevice
from app.memory.retrieval import MemoryContextService
from app.services.documents.access import authorized_history_context


class SupportContextService:
    async def build(
        self,
        session: AsyncSession,
        *,
        principal: Principal,
        conversation_id: UUID,
        current_message_id: UUID,
        query: str,
    ) -> SupportContext:
        conversation = await session.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.owner_id == principal.user_id,
            )
        )
        if conversation is None:
            raise LookupError("Conversation is unavailable to the current actor")
        device: DeviceContext | None = None
        if conversation.device_id is not None:
            row = await session.scalar(
                select(UserDevice).where(
                    UserDevice.id == conversation.device_id,
                    UserDevice.owner_id == principal.user_id,
                    UserDevice.active.is_(True),
                )
            )
            if row is not None:
                device = DeviceContext(id=row.id, label=row.label, platform=row.platform)
        recent_messages = list(
            (
                await session.scalars(
                    select(Message)
                    .where(
                        Message.conversation_id == conversation_id,
                        Message.id != current_message_id,
                    )
                    .order_by(Message.created_at.desc(), Message.id.desc())
                    .limit(120)
                )
            ).all()
        )
        history = await authorized_history_context(
            session,
            principal=principal,
            messages=list(reversed(recent_messages)),
        )
        memories = await MemoryContextService().context_messages(
            session,
            owner_id=principal.user_id,
            device_id=conversation.device_id,
        )
        return SupportContext(
            principal=principal,
            conversation_id=conversation_id,
            query=query.strip(),
            history=tuple(history),
            memories=tuple(memories),
            device=device,
        )
