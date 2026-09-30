"""Authenticated conversation and chat submission endpoints."""

from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pagination import CursorPage, PageLimit, build_page, decode_cursor
from app.auth.csrf import require_csrf
from app.db.models import Conversation, Message, MessageFeedback, RunStatus
from app.dependencies import CurrentPrincipal, get_db_session
from app.jobs.dispatch import BrokerUnavailableError, RunDispatcher
from app.memory.lifecycle import MemoryLifecycleService, MemoryNotFoundError
from app.prompts import SUPPORT_PROMPT_VERSION
from app.repositories.conversations import ConversationRepository
from app.services.conversations.submission import (
    ActiveRunConflictError,
    ConversationNotFoundError,
    RunRequestConflictError,
    RunSubmissionService,
)
from app.services.documents.access import redact_revoked_message_citations
from app.services.feedback import FeedbackService, FeedbackTargetNotFoundError

router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New support conversation", min_length=1, max_length=200)


class ConversationResponse(BaseModel):
    id: UUID
    title: str


class FeedbackResponse(BaseModel):
    id: UUID
    message_id: UUID
    rating: str
    reason: str | None
    comment: str | None


class MessageResponse(BaseModel):
    id: UUID
    run_id: UUID | None
    role: str
    content: str
    outcome: str | None
    citations: list[dict[str, object]]
    feedback: FeedbackResponse | None = None


class PutFeedbackRequest(BaseModel):
    rating: Literal["helpful", "unhelpful"]
    reason: str | None = Field(default=None, min_length=1, max_length=80)
    comment: str | None = Field(default=None, min_length=1, max_length=500)


class SubmitMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4_000)
    client_request_id: str = Field(min_length=8, max_length=80)


class SubmitMessageResponse(BaseModel):
    run_id: UUID
    status: RunStatus
    created: bool
    enqueued: bool
    enqueue_error: str | None


class SelectConversationDeviceRequest(BaseModel):
    device_id: UUID | None


def _conversation_response(value: Conversation) -> ConversationResponse:
    return ConversationResponse(id=value.id, title=value.title)


def _message_response(
    value: Message,
    override: tuple[str, str | None, list[dict[str, object]]] | None = None,
    feedback: MessageFeedback | None = None,
) -> MessageResponse:
    content, outcome, citations = override or (value.content, value.outcome, value.citations)
    return MessageResponse(
        id=value.id,
        run_id=value.run_id,
        role=value.role,
        content=content,
        outcome=outcome,
        citations=citations,
        feedback=_feedback_response(feedback) if feedback is not None else None,
    )


def _feedback_response(value: MessageFeedback) -> FeedbackResponse:
    return FeedbackResponse(
        id=value.id,
        message_id=value.message_id,
        rating=value.rating,
        reason=value.reason,
        comment=value.comment,
    )


@router.get("", response_model=CursorPage[ConversationResponse])
async def list_conversations(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: PageLimit = 20,
    cursor: str | None = None,
) -> CursorPage[ConversationResponse]:
    position = decode_cursor(cursor)
    values = await ConversationRepository().list_owned(
        session,
        owner_id=principal.user_id,
        limit=limit + 1,
        before=(position.timestamp, position.item_id) if position else None,
    )
    items, next_cursor = build_page(
        values,
        limit=limit,
        timestamp=lambda value: value.created_at,
    )
    return CursorPage[ConversationResponse](
        items=[_conversation_response(value) for value in items],
        next_cursor=next_cursor,
    )


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


@router.put(
    "/{conversation_id}/device",
    response_model=ConversationResponse,
    dependencies=[Depends(require_csrf)],
)
async def select_conversation_device(
    conversation_id: UUID,
    payload: SelectConversationDeviceRequest,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationResponse:
    try:
        conversation = await MemoryLifecycleService().assign_conversation_device(
            session,
            owner_id=principal.user_id,
            conversation_id=conversation_id,
            device_id=payload.device_id,
        )
        await session.commit()
    except MemoryNotFoundError as error:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return _conversation_response(conversation)


@router.get("/{conversation_id}/messages", response_model=CursorPage[MessageResponse])
async def list_messages(
    conversation_id: UUID,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: PageLimit = 20,
    cursor: str | None = None,
) -> CursorPage[MessageResponse]:
    repository = ConversationRepository()
    conversation = await repository.get_owned(
        session,
        conversation_id=conversation_id,
        owner_id=principal.user_id,
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    position = decode_cursor(cursor)
    values = await repository.list_messages_owned(
        session,
        conversation_id=conversation_id,
        owner_id=principal.user_id,
        limit=limit + 1,
        before=(position.timestamp, position.item_id) if position else None,
    )
    items, next_cursor = build_page(
        values,
        limit=limit,
        timestamp=lambda value: value.created_at,
    )
    redactions = await redact_revoked_message_citations(
        session,
        principal=principal,
        messages=items,
    )
    feedback = await FeedbackService().for_messages(
        session,
        owner_id=principal.user_id,
        message_ids=[value.id for value in items],
    )
    return CursorPage[MessageResponse](
        items=[
            _message_response(value, redactions.get(value.id), feedback.get(value.id))
            for value in reversed(items)
        ],
        next_cursor=next_cursor,
    )


@router.put(
    "/{conversation_id}/messages/{message_id}/feedback",
    response_model=FeedbackResponse,
    dependencies=[Depends(require_csrf)],
)
async def put_message_feedback(
    conversation_id: UUID,
    message_id: UUID,
    payload: PutFeedbackRequest,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FeedbackResponse:
    try:
        value = await FeedbackService().put(
            session,
            owner_id=principal.user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            rating=payload.rating,
            reason=payload.reason.strip() if payload.reason else None,
            comment=payload.comment.strip() if payload.comment else None,
        )
        await session.commit()
    except FeedbackTargetNotFoundError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant message not found",
        ) from error
    return _feedback_response(value)


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
            prompt_version=SUPPORT_PROMPT_VERSION,
            model=cast(str, request.app.state.settings.text_provider.value),
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
