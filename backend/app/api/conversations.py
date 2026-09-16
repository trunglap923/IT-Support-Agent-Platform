"""Authenticated conversation and chat submission endpoints."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import require_csrf
from app.db.models import Conversation, Message, RunStatus
from app.dependencies import CurrentPrincipal, get_db_session
from app.jobs.dispatch import BrokerUnavailableError, RunDispatcher
from app.repositories.conversations import ConversationRepository
from app.services.conversations.submission import (
    ActiveRunConflictError,
    ConversationNotFoundError,
    RunRequestConflictError,
    RunSubmissionService,
)
from app.services.documents.access import redact_revoked_message_citations

router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New support conversation", min_length=1, max_length=200)


class ConversationResponse(BaseModel):
    id: UUID
    title: str


class MessageResponse(BaseModel):
    id: UUID
    run_id: UUID | None
    role: str
    content: str
    outcome: str | None
    citations: list[dict[str, object]]


class SubmitMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4_000)
    client_request_id: str = Field(min_length=8, max_length=80)


class SubmitMessageResponse(BaseModel):
    run_id: UUID
    status: RunStatus
    created: bool
    enqueued: bool
    enqueue_error: str | None


def _conversation_response(value: Conversation) -> ConversationResponse:
    return ConversationResponse(id=value.id, title=value.title)


def _message_response(
    value: Message,
    override: tuple[str, str | None, list[dict[str, object]]] | None = None,
) -> MessageResponse:
    content, outcome, citations = override or (value.content, value.outcome, value.citations)
    return MessageResponse(
        id=value.id,
        run_id=value.run_id,
        role=value.role,
        content=content,
        outcome=outcome,
        citations=citations,
    )


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ConversationResponse]:
    values = await ConversationRepository().list_owned(session, owner_id=principal.user_id)
    return [_conversation_response(value) for value in values]


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_conversation(
    payload: CreateConversationRequest,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationResponse:
    conversation = await ConversationRepository().create(
        session,
        owner_id=principal.user_id,
        title=payload.title.strip(),
    )
    await session.commit()
    return _conversation_response(conversation)


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: UUID,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[MessageResponse]:
    repository = ConversationRepository()
    conversation = await repository.get_owned(
        session,
        conversation_id=conversation_id,
        owner_id=principal.user_id,
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    values = await repository.list_messages_owned(
        session,
        conversation_id=conversation_id,
        owner_id=principal.user_id,
    )
    redactions = await redact_revoked_message_citations(
        session,
        principal=principal,
        messages=values,
    )
    return [_message_response(value, redactions.get(value.id)) for value in values]


@router.post(
    "/{conversation_id}/messages",
    response_model=SubmitMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_csrf)],
)
async def submit_message(
    conversation_id: UUID,
    payload: SubmitMessageRequest,
    request: Request,
    principal: CurrentPrincipal,
) -> SubmitMessageResponse:
    database = request.app.state.database
    dispatcher = cast(RunDispatcher, request.app.state.run_dispatcher)
    try:
        result = await RunSubmissionService(database, dispatcher).submit(
            actor_id=principal.user_id,
            conversation_id=conversation_id,
            content=payload.content.strip(),
            client_request_id=payload.client_request_id,
            model=cast(str, request.app.state.settings.ai_provider.value),
        )
    except ConversationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        ) from error
    except (RunRequestConflictError, ActiveRunConflictError) as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except BrokerUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background worker is unavailable",
        ) from error
    return SubmitMessageResponse(
        run_id=result.run_id,
        status=result.status,
        created=result.created,
        enqueued=result.enqueued,
        enqueue_error=result.enqueue_error,
    )
