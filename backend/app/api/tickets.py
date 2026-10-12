"""Personal ticket reads and manual approval-draft creation."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.approval_checkpoint import ApprovalCheckpointError, pause_ticket_approval
from app.api.approvals import ApprovalResponse, approval_response
from app.api.pagination import CursorPage, PageLimit, build_page, decode_cursor
from app.auth.csrf import require_csrf
from app.auth.policies import require_roles
from app.db.models import (
    AgentRun,
    ApprovalRequest,
    Conversation,
    RunKind,
    RunStatus,
    Ticket,
    TicketIssueType,
    TicketSeverity,
    TicketStatus,
    User,
    UserRole,
)
from app.dependencies import CurrentPrincipal, get_database, get_db_session
from app.repositories.runs import RunRepository
from app.services.approvals import ApprovalArgumentsRejectedError, ApprovalService
from app.services.tickets import (
    TicketOperationConflictError,
    TicketOperationNotFoundError,
    TicketOperationService,
    TicketReadService,
)
from app.tools.schemas import CreateTicketArguments

router = APIRouter(prefix="/tickets", tags=["tickets"])


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_key: str
    title: str
    description: str
    issue_type: str
    severity: str
    status: str
    resolution_note: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    requester_name: str | None = None


class TicketTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["start", "resolve", "reopen"]
    expected_version: int = Field(ge=1)
    resolution_note: str | None = Field(default=None, max_length=4_000)


class TicketDraftRequest(CreateTicketArguments):
    client_request_id: str = Field(min_length=8, max_length=80)


class TicketDraftResponse(BaseModel):
    run_id: UUID
    approval: ApprovalResponse
    created: bool


class TicketSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total: int
    open: int
    in_progress: int
    resolved: int
    high_unresolved: int


async def _ticket_responses(session: AsyncSession, tickets: list[Ticket]) -> list[TicketResponse]:
    owner_ids = {ticket.owner_id for ticket in tickets}
    names: dict[UUID, str] = {}
    if owner_ids:
        result = await session.execute(
            select(User.id, User.display_name).where(User.id.in_(owner_ids))
        )
        names = dict(result.tuples().all())
    return [
        TicketResponse.model_validate(ticket).model_copy(
            update={"requester_name": names.get(ticket.owner_id)}
        )
        for ticket in tickets
    ]


@router.get("/mine", response_model=CursorPage[TicketResponse])
async def list_my_tickets(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: PageLimit = 20,
    cursor: str | None = None,
    ticket_status: TicketStatus | None = None,
    issue_type: TicketIssueType | None = None,
    severity: TicketSeverity | None = None,
) -> CursorPage[TicketResponse]:
    position = decode_cursor(cursor)
    tickets = await TicketReadService().list_owned(
        session,
        principal=principal,
        limit=limit + 1,
        before=(position.timestamp, position.item_id) if position else None,
        status=ticket_status,
        issue_type=issue_type,
        severity=severity,
    )
    items, next_cursor = build_page(tickets, limit=limit, timestamp=lambda value: value.updated_at)
    return CursorPage[TicketResponse](
        items=await _ticket_responses(session, items),
        next_cursor=next_cursor,
    )


@router.get("/mine/summary", response_model=TicketSummaryResponse)
async def summarize_my_tickets(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TicketSummaryResponse:
    summary = await TicketReadService().summarize_owned(session, principal=principal)
    return TicketSummaryResponse.model_validate(summary)


@router.get(
    "/queue",
    response_model=CursorPage[TicketResponse],
    dependencies=[Depends(require_roles(UserRole.IT, UserRole.ADMIN))],
)
async def list_ticket_queue(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    ticket_status: TicketStatus | None = None,
    issue_type: TicketIssueType | None = None,
    severity: TicketSeverity | None = None,
    limit: PageLimit = 20,
    cursor: str | None = None,
) -> CursorPage[TicketResponse]:
    position = decode_cursor(cursor)
    tickets = await TicketReadService().list_visible(
        session,
        principal=principal,
        status=ticket_status,
        limit=limit + 1,
        before=(position.timestamp, position.item_id) if position else None,
        issue_type=issue_type,
        severity=severity,
    )
    items, next_cursor = build_page(tickets, limit=limit, timestamp=lambda value: value.updated_at)
    return CursorPage[TicketResponse](
        items=await _ticket_responses(session, items),
        next_cursor=next_cursor,
    )


@router.get(
    "/queue/summary",
    response_model=TicketSummaryResponse,
    dependencies=[Depends(require_roles(UserRole.IT, UserRole.ADMIN))],
)
async def summarize_ticket_queue(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TicketSummaryResponse:
    summary = await TicketReadService().summarize_visible(session, principal=principal)
    return TicketSummaryResponse.model_validate(summary)


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: UUID,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TicketResponse:
    ticket = await TicketReadService().get_visible(
        session,
        principal=principal,
        ticket_id=ticket_id,
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket was not found")
    return (await _ticket_responses(session, [ticket]))[0]


@router.post(
    "/{ticket_id}/transition",
    response_model=TicketResponse,
    dependencies=[Depends(require_csrf), Depends(require_roles(UserRole.IT, UserRole.ADMIN))],
)
async def transition_ticket(
    ticket_id: UUID,
    payload: TicketTransitionRequest,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TicketResponse:
    try:
        ticket = await TicketOperationService().transition(
            session,
            principal=principal,
            ticket_id=ticket_id,
            action=payload.action,
            expected_version=payload.expected_version,
            resolution_note=payload.resolution_note,
        )
    except TicketOperationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ticket was not found"
        ) from error
    except TicketOperationConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    await session.commit()
    await session.refresh(ticket)
    return (await _ticket_responses(session, [ticket]))[0]


@router.post(
    "/drafts",
    response_model=TicketDraftResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_ticket_draft(
    payload: TicketDraftRequest,
    request: Request,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TicketDraftResponse:
    repository = RunRepository()
    existing_run = await repository.get_by_client_request(
        session,
        actor_id=principal.user_id,
        client_request_id=payload.client_request_id,
    )
    if existing_run is not None:
        existing_approval = await session.scalar(
            select(ApprovalRequest).where(ApprovalRequest.run_id == existing_run.id)
        )
        if existing_approval is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Draft is incomplete")
        return TicketDraftResponse(
            run_id=existing_run.id,
            approval=approval_response(existing_approval),
            created=False,
        )

    arguments = CreateTicketArguments.model_validate(
        payload.model_dump(exclude={"client_request_id"})
    )
    conversation = Conversation(owner_id=principal.user_id, title=arguments.title)
    session.add(conversation)
    await session.flush()
    run = AgentRun(
        conversation_id=conversation.id,
        actor_id=principal.user_id,
        kind=RunKind.MANUAL_TICKET,
        client_request_id=payload.client_request_id,
        input_hash=hashlib.sha256(arguments.model_dump_json().encode()).hexdigest(),
        status=RunStatus.WAITING_APPROVAL,
        checkpoint_thread_id=f"approval:{conversation.id}",
        prompt_version="manual-ticket-v1",
        model="none",
    )
    session.add(run)
    await session.flush()
    try:
        approval = await ApprovalService().create_ticket_draft(
            session,
            owner_id=principal.user_id,
            run_id=run.id,
            action_id=f"ticket:{run.id}",
            arguments=arguments,
        )
    except ApprovalArgumentsRejectedError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    await session.commit()

    database = get_database(request)
    try:
        await asyncio.to_thread(
            pause_ticket_approval,
            database_url=database.engine.url.render_as_string(hide_password=False),
            checkpoint_thread_id=run.checkpoint_thread_id,
            run_id=run.id,
            actor_id=principal.user_id,
            approval_id=approval.id,
            arguments_hash=approval.arguments_hash,
        )
    except ApprovalCheckpointError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Draft was saved but approval checkpoint is unavailable",
        ) from error
    return TicketDraftResponse(
        run_id=run.id,
        approval=approval_response(approval),
        created=True,
    )
