"""Role-protected simulated service-status operations API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import require_csrf
from app.auth.policies import require_roles
from app.config import Settings
from app.db.models import ServiceState, UserRole
from app.dependencies import CurrentPrincipal, get_db_session
from app.services.service_status import ServiceStatusNotFoundError, ServiceStatusService

router = APIRouter(prefix="/service-status", tags=["service-status"])


class ServiceStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service_id: str
    status: str
    message: str
    fault_mode: str
    updated_at: datetime


class ServiceStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["healthy", "degraded", "down", "unknown"]
    message: str = Field(min_length=3, max_length=500)
    fault_mode: Literal["none", "timeout", "error"] = "none"


def service_response(item: ServiceState) -> ServiceStateResponse:
    return ServiceStateResponse.model_validate(item)


@router.get(
    "",
    response_model=list[ServiceStateResponse],
    dependencies=[Depends(require_roles(UserRole.IT, UserRole.ADMIN))],
)
async def list_service_states(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[ServiceStateResponse]:
    items = await ServiceStatusService().list(session)
    return [service_response(item) for item in items]


@router.patch(
    "/{service_id}",
    response_model=ServiceStateResponse,
    dependencies=[Depends(require_csrf), Depends(require_roles(UserRole.ADMIN))],
)
async def update_service_state(
    service_id: str,
    payload: ServiceStateUpdate,
    request: Request,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ServiceStateResponse:
    settings = cast(Settings, request.app.state.settings)
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service simulation is disabled",
        )
    try:
        item = await ServiceStatusService().update(
            session,
            service_id=service_id,
            status=payload.status,
            message=payload.message,
            fault_mode=payload.fault_mode,
            updated_by=principal.user_id,
        )
    except ServiceStatusNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service was not found"
        ) from error
    await session.commit()
    await session.refresh(item)
    return service_response(item)
