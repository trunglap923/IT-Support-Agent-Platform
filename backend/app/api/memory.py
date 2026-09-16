"""Authenticated, owner-scoped memory settings and candidate API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import require_csrf
from app.dependencies import CurrentPrincipal, get_db_session
from app.memory.lifecycle import MemoryConflictError, MemoryLifecycleService

router = APIRouter(prefix="/memory", tags=["memory"])


class ConsentResponse(BaseModel):
    enabled: bool
    epoch: int


class UpdateConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    expected_epoch: int = Field(ge=0)


class MemoryCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    key: str
    value: str
    evidence: str
    status: str
    version: int
    expires_at: datetime


@router.get("/consent", response_model=ConsentResponse)
async def get_consent(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConsentResponse:
    value = await MemoryLifecycleService().get_consent(session, owner_id=principal.user_id)
    return ConsentResponse(enabled=value.enabled, epoch=value.epoch)


@router.put(
    "/consent",
    response_model=ConsentResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_consent(
    payload: UpdateConsentRequest,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConsentResponse:
    try:
        value = await MemoryLifecycleService().set_consent(
            session,
            owner_id=principal.user_id,
            enabled=payload.enabled,
            expected_epoch=payload.expected_epoch,
        )
        await session.commit()
    except MemoryConflictError as error:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return ConsentResponse(enabled=value.enabled, epoch=value.epoch)


@router.get("/candidates", response_model=list[MemoryCandidateResponse])
async def list_memory_candidates(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[MemoryCandidateResponse]:
    values = await MemoryLifecycleService().list_pending_candidates(
        session, owner_id=principal.user_id
    )
    return [MemoryCandidateResponse.model_validate(value) for value in values]
