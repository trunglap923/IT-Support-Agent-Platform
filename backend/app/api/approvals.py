"""Owner-scoped approval read and decision API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import require_csrf
from app.db.models import ApprovalRequest
from app.dependencies import CurrentPrincipal, get_db_session
from app.services.approvals import (
    ApprovalConflictError,
    ApprovalExpiredError,
    ApprovalNotFoundError,
    ApprovalService,
)

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
    return approval_response(approval)
