"""Personal ticket reads and manual approval-draft creation."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.approval_checkpoint import ApprovalCheckpointError, pause_ticket_approval
from app.api.approvals import ApprovalResponse, approval_response
from app.auth.csrf import require_csrf
from app.db.models import AgentRun, ApprovalRequest, Conversation, RunKind, RunStatus
from app.dependencies import CurrentPrincipal, get_database, get_db_session
from app.repositories.runs import RunRepository
from app.services.approvals import ApprovalService
from app.services.tickets import TicketReadService
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


class TicketDraftRequest(CreateTicketArguments):
    client_request_id: str = Field(min_length=8, max_length=80)


class TicketDraftResponse(BaseModel):
    run_id: UUID
    approval: ApprovalResponse
    created: bool


@router.get("/mine", response_model=list[TicketResponse])
async def list_my_tickets(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[TicketResponse]:
    tickets = await TicketReadService().list_owned(session, principal=principal)
    return [TicketResponse.model_validate(ticket) for ticket in tickets]


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
    approval = await ApprovalService().create_ticket_draft(
        session,
        owner_id=principal.user_id,
        run_id=run.id,
        action_id=f"ticket:{run.id}",
        arguments=arguments,
    )
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
