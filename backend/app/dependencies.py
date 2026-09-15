"""FastAPI dependencies for process-local resources."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.auth.sessions import hash_token, principal_from_session
from app.config import Settings
from app.db import Database
from app.repositories.sessions import SessionRepository


def get_database(request: Request) -> Database:
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not configured",
        )
    return cast(Database, database)


async def get_db_session(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    async with database.session() as session:
        yield session


async def get_current_principal(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session, scope="function")],
) -> Principal:
    settings = cast(Settings, request.app.state.settings)
    cookie_token = request.cookies.get(settings.session_cookie_name)
    if not cookie_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    auth_session = await SessionRepository().get_active_by_token_hash(
        session,
        token_hash=hash_token(cookie_token),
        now=datetime.now(UTC),
    )
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    request.state.csrf_token_hash = auth_session.csrf_token_hash
    return principal_from_session(auth_session)


DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]
