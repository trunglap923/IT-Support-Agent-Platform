"""Procedure retrieval plus IT/Admin candidate review and publication API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context.contracts import ContextScope
from app.auth.csrf import require_csrf
from app.auth.policies import require_roles
from app.db.models import (
    Procedure,
    ProcedureApplicability,
    ProcedureExecution,
    ProcedureStep,
    ProcedureVersion,
    UserRole,
)
from app.dependencies import CurrentPrincipal, get_db_session
from app.procedures.contracts import (
    ProcedureCandidateDefinition,
    ProcedureReviewDecision,
)
from app.procedures.registry import (
    ProcedureConflictError,
    ProcedureNotFoundError,
    ProcedureRegistryService,
)
from app.procedures.retrieval import ProcedureRetriever

router = APIRouter(prefix="/procedures", tags=["procedures"])


class ProcedureStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_key: str
    ordinal: int
    action: str
    tool_name: str | None
    expected_observation: str
    approval_required: bool
    verification: str | None


class ApplicabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    signal_type: str
    signal_value: str


class ProcedureVersionResponse(BaseModel):
    id: UUID
    procedure_id: UUID
    key: str
    title: str
    intent: str
    description: str
    version_number: int
    status: str
    visibility: str
    department_id: UUID | None
    applicability: list[ApplicabilityResponse]
    prerequisites: list[str]
    prohibited_actions: list[str]
    evidence_refs: list[str]
    source_document_version_id: UUID | None
    success_count: int
    failure_count: int
    effective_from: datetime | None
    effective_to: datetime | None
    approved_by: UUID | None
    validation_report: dict[str, Any]
    steps: list[ProcedureStepResponse]


class ProcedureMatchResponse(BaseModel):
    version_id: UUID
    content: str
    matched_signals: list[str]


class ProcedureMetricsResponse(BaseModel):
    approved_versions: int
    candidate_versions: int
    completed_executions: int
    verified_successes: int
    failures: int
    stale_source_versions: int


def _procedure_error(error: ProcedureConflictError | ProcedureNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_404_NOT_FOUND
            if isinstance(error, ProcedureNotFoundError)
            else status.HTTP_409_CONFLICT
        ),
        detail=str(error),
    )


async def _response(session: AsyncSession, version: ProcedureVersion) -> ProcedureVersionResponse:
    procedure = await session.get(Procedure, version.procedure_id)
    if procedure is None:
        raise ProcedureNotFoundError("Procedure not found")
    applicability = list(
        await session.scalars(
            select(ProcedureApplicability)
            .where(ProcedureApplicability.procedure_version_id == version.id)
            .order_by(ProcedureApplicability.signal_type, ProcedureApplicability.signal_value)
        )
    )
    steps = list(
        await session.scalars(
            select(ProcedureStep)
            .where(ProcedureStep.procedure_version_id == version.id)
            .order_by(ProcedureStep.ordinal)
        )
    )
    return ProcedureVersionResponse(
        id=version.id,
        procedure_id=procedure.id,
        key=procedure.key,
        title=procedure.title,
        intent=procedure.intent,
        description=procedure.description,
        version_number=version.version_number,
        status=version.status,
        visibility=version.visibility,
        department_id=version.department_id,
        applicability=[ApplicabilityResponse.model_validate(item) for item in applicability],
        prerequisites=list(version.prerequisites),
        prohibited_actions=list(version.prohibited_actions),
        evidence_refs=list(version.evidence_refs),
        source_document_version_id=version.source_document_version_id,
        success_count=version.success_count,
        failure_count=version.failure_count,
        effective_from=version.effective_from,
        effective_to=version.effective_to,
        approved_by=version.approved_by,
        validation_report=dict(version.validation_report),
        steps=[ProcedureStepResponse.model_validate(item) for item in steps],
    )


@router.get("", response_model=list[ProcedureMatchResponse])
async def retrieve_procedures(
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    query: Annotated[str, Query(min_length=2, max_length=500)],
) -> list[ProcedureMatchResponse]:
    matches = await ProcedureRetriever().retrieve(
        session,
        principal=principal,
        query=query,
        scope=ContextScope(
            owner_id=principal.user_id,
            department_id=principal.department_id,
        ),
    )
    return [
        ProcedureMatchResponse(
            version_id=item.version_id,
            content=item.candidate.content,
            matched_signals=list(item.matched_signals),
        )
        for item in matches
    ]


@router.get(
    "/admin/versions",
    response_model=list[ProcedureVersionResponse],
    dependencies=[Depends(require_roles(UserRole.IT, UserRole.ADMIN))],
)
async def list_versions(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    version_status: Literal["candidate", "review", "approved", "deprecated", "rejected"]
    | None = None,
    limit: int = 50,
) -> list[ProcedureVersionResponse]:
    statement = select(ProcedureVersion).order_by(
        ProcedureVersion.created_at.desc(), ProcedureVersion.id.desc()
    )
    if version_status is not None:
        statement = statement.where(ProcedureVersion.status == version_status)
    values = list(await session.scalars(statement.limit(min(max(limit, 1), 100))))
    return [await _response(session, item) for item in values]


@router.post(
    "/admin/candidates",
    response_model=ProcedureVersionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf), Depends(require_roles(UserRole.IT, UserRole.ADMIN))],
)
async def create_candidate(
    payload: ProcedureCandidateDefinition,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProcedureVersionResponse:
    try:
        value = await ProcedureRegistryService().create_candidate(
            session,
            definition=payload,
            created_by=principal.user_id,
            technician_authored=True,
        )
        await session.commit()
    except (ProcedureConflictError, ProcedureNotFoundError) as error:
        await session.rollback()
        raise _procedure_error(error) from error
    return await _response(session, value)


@router.post(
    "/admin/versions/{version_id}/submit",
    response_model=ProcedureVersionResponse,
    dependencies=[Depends(require_csrf), Depends(require_roles(UserRole.IT, UserRole.ADMIN))],
)
async def submit_version(
    version_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProcedureVersionResponse:
    try:
        value = await ProcedureRegistryService().submit_for_review(session, version_id=version_id)
        await session.commit()
    except (ProcedureConflictError, ProcedureNotFoundError) as error:
        await session.rollback()
        raise _procedure_error(error) from error
    return await _response(session, value)


@router.post(
    "/admin/versions/{version_id}/review",
    response_model=ProcedureVersionResponse,
    dependencies=[Depends(require_csrf), Depends(require_roles(UserRole.IT, UserRole.ADMIN))],
)
async def review_version(
    version_id: UUID,
    payload: ProcedureReviewDecision,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProcedureVersionResponse:
    try:
        value = await ProcedureRegistryService().review(
            session,
            version_id=version_id,
            reviewer_id=principal.user_id,
            review=payload,
        )
        await session.commit()
    except (ProcedureConflictError, ProcedureNotFoundError) as error:
        await session.rollback()
        raise _procedure_error(error) from error
    return await _response(session, value)


@router.get(
    "/admin/metrics",
    response_model=ProcedureMetricsResponse,
    dependencies=[Depends(require_roles(UserRole.IT, UserRole.ADMIN))],
)
async def procedure_metrics(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProcedureMetricsResponse:
    async def count_versions(value: str) -> int:
        result = await session.scalar(
            select(func.count())
            .select_from(ProcedureVersion)
            .where(ProcedureVersion.status == value)
        )
        return int(result or 0)

    completed = await session.scalar(
        select(func.count())
        .select_from(ProcedureExecution)
        .where(ProcedureExecution.status == "completed")
    )
    successes = await session.scalar(
        select(func.count())
        .select_from(ProcedureExecution)
        .where(
            ProcedureExecution.outcome == "success",
            ProcedureExecution.verified.is_(True),
        )
    )
    failures = await session.scalar(
        select(func.count())
        .select_from(ProcedureExecution)
        .where(ProcedureExecution.outcome == "failure")
    )
    stale = await ProcedureRegistryService().stale_versions(session)
    return ProcedureMetricsResponse(
        approved_versions=await count_versions("approved"),
        candidate_versions=await count_versions("candidate"),
        completed_executions=int(completed or 0),
        verified_successes=int(successes or 0),
        failures=int(failures or 0),
        stale_source_versions=len(stale),
    )
