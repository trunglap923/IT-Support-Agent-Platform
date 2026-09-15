"""Authentication and opaque session lifecycle."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import verify_dummy_password, verify_password
from app.auth.principal import Principal
from app.db.models import AuthSession, User
from app.repositories.sessions import SessionRepository
from app.repositories.users import UserRepository


@dataclass(frozen=True, slots=True)
class NewSession:
    session_token: str
    csrf_token: str
    expires_at: datetime
    principal: Principal


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def principal_from_session(auth_session: AuthSession) -> Principal:
    user = auth_session.user
    return Principal(
        user_id=user.id,
        session_id=auth_session.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        department_id=user.department_id,
        department_key=user.department.key,
    )


async def authenticate_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> User | None:
    user = await UserRepository().get_by_email(session, email)
    if user is None:
        verify_dummy_password(password)
        return None
    if not verify_password(password, user.password_hash) or not user.active:
        return None
    return user


async def create_session(
    session: AsyncSession,
    *,
    user: User,
    ttl_hours: int,
    now: datetime | None = None,
) -> NewSession:
    issued_at = now or datetime.now(UTC)
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    auth_session = AuthSession(
        token_hash=hash_token(session_token),
        user_id=user.id,
        csrf_token_hash=hash_token(csrf_token),
        expires_at=issued_at + timedelta(hours=ttl_hours),
        revoked_at=None,
    )
    auth_session.user = user
    SessionRepository().add(session, auth_session)
    await session.flush()
    return NewSession(
        session_token=session_token,
        csrf_token=csrf_token,
        expires_at=auth_session.expires_at,
        principal=principal_from_session(auth_session),
    )
