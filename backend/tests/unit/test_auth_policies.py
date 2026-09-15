from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.auth.policies import authorize_roles, require_roles
from app.auth.principal import Principal
from app.config import AppEnvironment, Settings
from app.db.models import UserRole


def principal(role: UserRole) -> Principal:
    return Principal(
        user_id=uuid4(),
        session_id=uuid4(),
        email="demo@example.com",
        display_name="Demo",
        role=role,
        department_id=uuid4(),
        department_key="engineering",
    )


def test_role_policy_allows_matching_role() -> None:
    authorize_roles(principal(UserRole.IT), frozenset({UserRole.IT, UserRole.ADMIN}))


def test_role_policy_rejects_employee() -> None:
    with pytest.raises(HTTPException) as error:
        authorize_roles(principal(UserRole.EMPLOYEE), frozenset({UserRole.ADMIN}))
    assert error.value.status_code == 403


def test_role_dependency_requires_at_least_one_role() -> None:
    with pytest.raises(ValueError, match="At least one role"):
        require_roles()


def test_production_requires_secure_cookie() -> None:
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        Settings(app_env=AppEnvironment.PRODUCTION, cookie_secure=False)
