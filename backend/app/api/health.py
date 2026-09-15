"""Process health endpoint.

Dependency readiness checks are added with PostgreSQL and Redis in WP-02/WP-03.
"""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.config import Settings

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    provider: str
    request_id: str


async def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


@router.get("/live", response_model=LiveResponse)
async def live(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> LiveResponse:
    """Report that the API process and configuration loaded successfully."""

    return LiveResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env.value,
        provider=settings.ai_provider.value,
        request_id=request.state.request_id,
    )
