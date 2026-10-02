"""Owner-scoped approval read and decision API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pagination import CursorPage, PageLimit, build_page, decode_cursor
from app.auth.csrf import require_csrf
from app.db.models import (
    AgentRun,
    AgentRuntimeState,
    ApprovalRequest,
    ApprovalStatus,
    Message,
    RunStatus,
)
from app.dependencies import CurrentPrincipal, get_db_session
from app.jobs.dispatch import BrokerUnavailableError, RunDispatcher
from app.repositories.conversations import ConversationRepository
from app.services.approvals import (
    ApprovalConflictError,
    ApprovalExpiredError,
    ApprovalNotFoundError,
    ApprovalService,
)
from app.services.conversations.run_state import RunStateService

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action_id: str
    run_id: UUID
    tool_name: str
    canonical_args: dict[str, object]
    arguments_hash: str
    schema_version: int
    status: str
    version: int
    expires_at: datetime


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    expected_version: int = Field(ge=1)


def approval_response(approval: ApprovalRequest) -> ApprovalResponse:
    return ApprovalResponse.model_validate(approval)


@router.get("", response_model=CursorPage[ApprovalResponse])
async def list_approvals(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    approval_status: ApprovalStatus | None = None,
    limit: PageLimit = 20,
    cursor: str | None = None,
) -> CursorPage[ApprovalResponse]:
    position = decode_cursor(cursor)
    approvals = await ApprovalService().list_owned(
        session,
        owner_id=principal.user_id,
        status=approval_status,
        limit=limit + 1,
        before=(position.timestamp, position.item_id) if position else None,
    )
    items, next_cursor = build_page(
        approvals,
        limit=limit,
        timestamp=lambda value: value.created_at,
    )
    return CursorPage[ApprovalResponse](
        items=[approval_response(approval) for approval in items],
        next_cursor=next_cursor,
    )


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: UUID,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApprovalResponse:
    approval = await ApprovalService().get_owned(
        session, approval_id=approval_id, owner_id=principal.user_id
    )
    if approval is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval was not found")
    return approval_response(approval)


@router.post(
    "/{approval_id}/decision",
    response_model=ApprovalResponse,
    dependencies=[Depends(require_csrf)],
)
async def decide_approval(
    approval_id: UUID,
    payload: ApprovalDecisionRequest,
    request: Request,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ApprovalResponse:
    try:
        approval = await ApprovalService().decide(
            session,
            approval_id=approval_id,
            owner_id=principal.user_id,
            decision=payload.decision,
            expected_version=payload.expected_version,
        )
        runtime_state = await session.get(AgentRuntimeState, approval.run_id)
        resume_agent = (
            runtime_state is not None
            and runtime_state.runtime == "openai_agents"
            and runtime_state.status == "paused"
        )
        await RunStateService().transition(
            session,
            run_id=approval.run_id,
            actor_id=principal.user_id,
            target=(
                RunStatus.RESUME_QUEUED
                if payload.decision == "approve" or resume_agent
                else RunStatus.COMPLETED
            ),
            operation_id=f"approval-decision:{approval.id}",
            outcome="approval_rejected" if payload.decision == "reject" else None,
            safe_payload={
                "approval_id": str(approval.id),
                "decision": payload.decision,
            },
        )
        if payload.decision == "reject" and not resume_agent:
            run = await session.get(AgentRun, approval.run_id)
            if run is not None:
                await ConversationRepository().touch(session, conversation_id=run.conversation_id)
                session.add(
                    Message(
                        conversation_id=run.conversation_id,
                        run_id=run.id,
                        role="assistant",
                        content="Bạn đã từ chối bản nháp; hệ thống không tạo ticket.",
                        outcome="approval_rejected",
                        citations=[],
                    )
                )
    except ApprovalNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Approval was not found"
        ) from error
    except ApprovalExpiredError as error:
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Approval has expired"
        ) from error
    except ApprovalConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    await session.commit()
    if payload.decision == "approve" or resume_agent:
        dispatcher = cast(RunDispatcher, request.app.state.run_dispatcher)
        try:
            await dispatcher.enqueue_run(approval.run_id)
        except BrokerUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Approval was saved but resume delivery is unavailable",
            ) from error
    return approval_response(approval)
