"""Session-cookie authentication endpoints."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.csrf import require_csrf, require_trusted_origin
from app.auth.policies import require_roles
from app.auth.principal import Principal
from app.auth.rate_limit import (
    LoginRateLimiter,
    LoginRateLimitExceeded,
    LoginRateLimitUnavailable,
)
from app.auth.sessions import authenticate_user, create_session, hash_token
from app.config import Settings
from app.db.models import UserRole
from app.dependencies import CurrentPrincipal, get_db_session
from app.repositories.sessions import SessionRepository

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: UserRole
    department_id: UUID
    department_key: str


class LoginResponse(BaseModel):
    user: UserResponse
    csrf_token: str
    expires_at: datetime


class CurrentSessionResponse(BaseModel):
    user: UserResponse
    csrf_token: str


def user_response(principal: Principal) -> UserResponse:
    return UserResponse(
        id=principal.user_id,
        email=principal.email,
        display_name=principal.display_name,
        role=principal.role,
        department_id=principal.department_id,
        department_key=principal.department_key,
    )


def set_auth_cookies(
    response: Response,
    *,
    settings: Settings,
    session_token: str,
    csrf_token: str,
    max_age: int,
) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LoginResponse:
    settings = cast(Settings, request.app.state.settings)
    limiter: LoginRateLimiter | None = None
    client_identifier = request.client.host if request.client is not None else "unknown"
    if settings.auth_login_rate_limit_enabled:
        redis_client = cast(Redis | None, getattr(request.app.state, "redis", None))
        if redis_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication protection is unavailable",
            )
        limiter = LoginRateLimiter(
            redis_client,
            max_attempts=settings.auth_login_max_attempts,
            window_seconds=settings.auth_login_window_seconds,
        )
        try:
            await limiter.consume(
                email=payload.email,
                client_identifier=client_identifier,
            )
        except LoginRateLimitExceeded as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts",
                headers={"Retry-After": str(error.retry_after_seconds)},
            ) from error
        except LoginRateLimitUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication protection is unavailable",
            ) from error

    user = await authenticate_user(session, email=payload.email, password=payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if limiter is not None:
        try:
            await limiter.reset(
                email=payload.email,
                client_identifier=client_identifier,
            )
        except LoginRateLimitUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication protection is unavailable",
            ) from error
    new_session = await create_session(
        session,
        user=user,
        ttl_hours=settings.session_ttl_hours,
    )
    await session.commit()
    set_auth_cookies(
        response,
        settings=settings,
        session_token=new_session.session_token,
        csrf_token=new_session.csrf_token,
        max_age=settings.session_ttl_hours * 3600,
    )
    return LoginResponse(
        user=user_response(new_session.principal),
        csrf_token=new_session.csrf_token,
        expires_at=new_session.expires_at,
    )


@router.get("/me", response_model=CurrentSessionResponse)
async def me(request: Request, principal: CurrentPrincipal) -> CurrentSessionResponse:
    settings = cast(Settings, request.app.state.settings)
    csrf_token = request.cookies.get(settings.csrf_cookie_name)
    expected_hash = getattr(request.state, "csrf_token_hash", None)
    if (
        not csrf_token
        or not expected_hash
        or not secrets.compare_digest(hash_token(csrf_token), expected_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return CurrentSessionResponse(user=user_response(principal), csrf_token=csrf_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def logout(
    request: Request,
    response: Response,
    principal: CurrentPrincipal,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    settings = cast(Settings, request.app.state.settings)
    await SessionRepository().revoke(
        session,
        session_id=principal.session_id,
        revoked_at=datetime.now(UTC),
    )
    await session.commit()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        settings.csrf_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
    )


@router.get(
    "/admin-check",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def admin_check() -> None:
    """Small protected contract endpoint; admin UI is implemented in WP-11."""
