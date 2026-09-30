"""Authenticated, owner-scoped memory settings and candidate API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.pagination import CursorPage, PageLimit, build_page, decode_cursor
from app.auth.csrf import require_csrf
from app.dependencies import CurrentPrincipal, get_db_session
from app.memory.lifecycle import (
    MemoryConflictError,
    MemoryLifecycleService,
    MemoryNotFoundError,
)

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    key: str
    value: str
    evidence: str
    device_id: UUID | None
    status: str
    version: int
    expires_at: datetime


class CreateDeviceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=80)
    platform: Literal["windows", "macos", "linux", "other"]


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str
    platform: str
    active: bool
    version: int


class CandidateDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    device_id: UUID | None = None
    corrected_value: str | None = Field(default=None, min_length=1, max_length=240)


class MemoryFactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    key: str
    value: str
    scope: str
    device_id: UUID | None
    version: int
    expires_at: datetime


class UpdateFactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    value: str = Field(min_length=1, max_length=240)


@router.get("/candidates", response_model=CursorPage[MemoryCandidateResponse])
async def list_memory_candidates(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: PageLimit = 20,
    cursor: str | None = None,
) -> CursorPage[MemoryCandidateResponse]:
    position = decode_cursor(cursor)
    values = await MemoryLifecycleService().list_pending_candidates(
        session,
        owner_id=principal.user_id,
        limit=limit + 1,
        after=(position.timestamp, position.item_id) if position else None,
    )
    items, next_cursor = build_page(
        values,
        limit=limit,
        timestamp=lambda value: value.created_at,
    )
    return CursorPage[MemoryCandidateResponse](
        items=[MemoryCandidateResponse.model_validate(value) for value in items],
        next_cursor=next_cursor,
    )


@router.get("/devices", response_model=list[DeviceResponse])
async def list_devices(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[DeviceResponse]:
    values = await MemoryLifecycleService().list_devices(session, owner_id=principal.user_id)
    return [DeviceResponse.model_validate(value) for value in values]


@router.post(
    "/devices",
    response_model=DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_device(
    payload: CreateDeviceRequest,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DeviceResponse:
    value = await MemoryLifecycleService().create_device(
        session,
        owner_id=principal.user_id,
        label=payload.label,
        platform=payload.platform,
    )
    await session.commit()
    return DeviceResponse.model_validate(value)


def _memory_error(error: MemoryConflictError | MemoryNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_404_NOT_FOUND
            if isinstance(error, MemoryNotFoundError)
            else status.HTTP_409_CONFLICT
        ),
        detail=str(error),
    )


@router.post(
    "/candidates/{candidate_id}/confirm",
    response_model=MemoryFactResponse,
    dependencies=[Depends(require_csrf)],
)
async def confirm_candidate(
    candidate_id: UUID,
    payload: CandidateDecisionRequest,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MemoryFactResponse:
    try:
        value = await MemoryLifecycleService().confirm_candidate(
            session,
            owner_id=principal.user_id,
            candidate_id=candidate_id,
            expected_version=payload.expected_version,
            device_id=payload.device_id,
            corrected_value=payload.corrected_value,
        )
        await session.commit()
    except (MemoryConflictError, MemoryNotFoundError) as error:
        await session.rollback()
        raise _memory_error(error) from error
    return MemoryFactResponse.model_validate(value)


@router.post(
    "/candidates/{candidate_id}/reject",
    response_model=MemoryCandidateResponse,
    dependencies=[Depends(require_csrf)],
)
async def reject_candidate(
    candidate_id: UUID,
    payload: CandidateDecisionRequest,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MemoryCandidateResponse:
    try:
        value = await MemoryLifecycleService().reject_candidate(
            session,
            owner_id=principal.user_id,
            candidate_id=candidate_id,
            expected_version=payload.expected_version,
        )
        await session.commit()
    except (MemoryConflictError, MemoryNotFoundError) as error:
        await session.rollback()
        raise _memory_error(error) from error
    return MemoryCandidateResponse.model_validate(value)


@router.get("/facts", response_model=CursorPage[MemoryFactResponse])
async def list_facts(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: PageLimit = 20,
    cursor: str | None = None,
) -> CursorPage[MemoryFactResponse]:
    position = decode_cursor(cursor)
    values = await MemoryLifecycleService().list_facts(
        session,
        owner_id=principal.user_id,
        limit=limit + 1,
        before=(position.timestamp, position.item_id) if position else None,
    )
    items, next_cursor = build_page(
        values,
        limit=limit,
        timestamp=lambda value: value.updated_at,
    )
    return CursorPage[MemoryFactResponse](
        items=[MemoryFactResponse.model_validate(value) for value in items],
        next_cursor=next_cursor,
    )


@router.patch(
    "/facts/{fact_id}",
    response_model=MemoryFactResponse,
    dependencies=[Depends(require_csrf)],
)
async def update_fact(
    fact_id: UUID,
    payload: UpdateFactRequest,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MemoryFactResponse:
    try:
        value = await MemoryLifecycleService().update_fact(
            session,
            owner_id=principal.user_id,
            fact_id=fact_id,
            expected_version=payload.expected_version,
            value=payload.value,
        )
        await session.commit()
    except (MemoryConflictError, MemoryNotFoundError) as error:
        await session.rollback()
        raise _memory_error(error) from error
    return MemoryFactResponse.model_validate(value)


@router.delete(
    "/facts/{fact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_fact(
    fact_id: UUID,
    expected_version: int,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    try:
        await MemoryLifecycleService().delete_fact(
            session,
            owner_id=principal.user_id,
            fact_id=fact_id,
            expected_version=expected_version,
        )
        await session.commit()
    except (MemoryConflictError, MemoryNotFoundError) as error:
        await session.rollback()
        raise _memory_error(error) from error
