"""Origin and synchronizer-token protection for cookie-authenticated writes."""

from __future__ import annotations

import secrets
from typing import Annotated, cast

from fastapi import Depends, Header, HTTPException, Request, status

from app.auth.principal import Principal
from app.auth.sessions import hash_token
from app.config import Settings
from app.dependencies import get_current_principal


def require_trusted_origin(request: Request) -> None:
    settings = cast(Settings, request.app.state.settings)
    origin = request.headers.get("origin")
    if origin != settings.allowed_web_origin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Untrusted request origin",
        )


async def require_csrf(
    request: Request,
    _principal: Annotated[Principal, Depends(get_current_principal)],
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    require_trusted_origin(request)
    settings = cast(Settings, request.app.state.settings)
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    expected_hash = getattr(request.state, "csrf_token_hash", None)
    if not csrf_header or not csrf_cookie or not expected_hash:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    if not secrets.compare_digest(csrf_header, csrf_cookie) or not secrets.compare_digest(
        hash_token(csrf_header), expected_hash
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
