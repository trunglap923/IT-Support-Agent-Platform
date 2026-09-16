"""Process liveness and dependency readiness endpoints."""

import asyncio
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.asyncio import Redis

from app.config import Settings
from app.db import Database

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    provider: str
    request_id: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: dict[str, Literal["up", "down", "not_configured"]]


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


async def check_dependency(check: object, *, timeout_seconds: float) -> bool:
    try:
        async with asyncio.timeout(timeout_seconds):
            if isinstance(check, Database):
                await check.ping()
            else:
                await cast(Redis, check).ping()
    except Exception:
        return False
    return True


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def ready(request: Request) -> ReadinessResponse | Response:
    """Report PostgreSQL/Redis reachability without contacting model providers."""

    settings = cast(Settings, request.app.state.settings)
    database = cast(Database | None, getattr(request.app.state, "database", None))
    redis_client = cast(Redis | None, getattr(request.app.state, "redis", None))
    dependencies: dict[str, Literal["up", "down", "not_configured"]] = {
        "postgres": "not_configured",
        "redis": "not_configured",
    }
    if database is not None:
        dependencies["postgres"] = (
            "up"
            if await check_dependency(
                database,
                timeout_seconds=settings.readiness_timeout_seconds,
            )
            else "down"
        )
    if redis_client is not None:
        dependencies["redis"] = (
            "up"
            if await check_dependency(
                redis_client,
                timeout_seconds=settings.readiness_timeout_seconds,
            )
            else "down"
        )

    is_ready = all(value == "up" for value in dependencies.values())
    payload = ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        dependencies=dependencies,
    )
    if not is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(),
        )
    return payload
