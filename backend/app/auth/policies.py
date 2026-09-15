"""Reusable role authorization dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.auth.principal import Principal
from app.db.models import UserRole
from app.dependencies import get_current_principal


def authorize_roles(principal: Principal, allowed_roles: frozenset[UserRole]) -> None:
    if principal.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")


def require_roles(*allowed_roles: UserRole) -> Callable[..., None]:
    allowed = frozenset(allowed_roles)
    if not allowed:
        raise ValueError("At least one role is required")

    def dependency(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> None:
        authorize_roles(principal, allowed)

    return dependency
