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
from app.auth.policies import require_roles
from app.db.models import UserRole
from app.dependencies import CurrentPrincipal, get_db_session
from app.memory.audit import MemoryAuditService
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
    created_at: datetime
    updated_at: datetime


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


class MemoryDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    operation: str
    status: str
    policy_version: str
    reason_code: str
    created_at: datetime


class MemoryFactExplanationResponse(BaseModel):
    assertion_id: UUID
    predicate: str
    status: str
    authority_tier: int
    confidence: float
    source_type: str
    source_ref: str
    observed_at: datetime
    decisions: list[MemoryDecisionResponse]


class EpisodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    summary: str
    outcome: str
    verified: bool
    service_ids: list[str]
    error_codes: list[str]
    completed_at: datetime


class ConflictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    subject_type: str
    predicate: str
    assertion_a_id: UUID
    assertion_b_id: UUID
    status: str
    resolution: str | None
    selected_assertion_id: UUID | None
    created_at: datetime


class ResolveConflictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_assertion_id: UUID


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


@router.get("/facts/{fact_id}/explanation", response_model=MemoryFactExplanationResponse)
async def explain_fact(
    fact_id: UUID,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MemoryFactExplanationResponse:
    try:
        assertion, source, decisions = await MemoryAuditService().explain_fact(
            session, owner_id=principal.user_id, fact_id=fact_id
        )
    except (MemoryConflictError, MemoryNotFoundError) as error:
        raise _memory_error(error) from error
    return MemoryFactExplanationResponse(
        assertion_id=assertion.id,
        predicate=assertion.predicate,
        status=assertion.status,
        authority_tier=assertion.authority_tier,
        confidence=float(assertion.confidence),
        source_type=source.source_type,
        source_ref=source.source_ref,
        observed_at=source.observed_at,
        decisions=[MemoryDecisionResponse.model_validate(item) for item in decisions],
    )


@router.get("/episodes", response_model=list[EpisodeResponse])
async def list_episodes(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = 20,
) -> list[EpisodeResponse]:
    values = await MemoryAuditService().list_episodes(
        session, owner_id=principal.user_id, limit=min(max(limit, 1), 100)
    )
    return [EpisodeResponse.model_validate(item) for item in values]


@router.get(
    "/admin/conflicts",
    response_model=list[ConflictResponse],
    dependencies=[Depends(require_roles(UserRole.IT, UserRole.ADMIN))],
)
async def list_conflicts(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    conflict_status: Literal["pending", "quarantined"] = "quarantined",
) -> list[ConflictResponse]:
    del principal
    values = await MemoryAuditService().list_conflicts(session, status=conflict_status)
    return [ConflictResponse.model_validate(item) for item in values]


@router.post(
    "/admin/conflicts/{conflict_id}/resolve",
    response_model=ConflictResponse,
    dependencies=[Depends(require_csrf), Depends(require_roles(UserRole.IT, UserRole.ADMIN))],
)
async def resolve_conflict(
    conflict_id: UUID,
    payload: ResolveConflictRequest,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConflictResponse:
    try:
        value = await MemoryAuditService().resolve_conflict(
            session,
            conflict_id=conflict_id,
            selected_assertion_id=payload.selected_assertion_id,
            reviewer_id=principal.user_id,
        )
        await session.commit()
    except (MemoryConflictError, MemoryNotFoundError) as error:
        await session.rollback()
        raise _memory_error(error) from error
    return ConflictResponse.model_validate(value)


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
