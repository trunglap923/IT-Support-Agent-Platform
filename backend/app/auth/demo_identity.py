"""Idempotent departments and accounts for the standalone portfolio demo."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password, validate_password, verify_password
from app.db.models import Department, User, UserRole
from app.repositories.users import UserRepository

DEMO_EMAIL = "employee.engineering@example.com"
DEMO_DEPARTMENT_KEY = "engineering"


@dataclass(frozen=True, slots=True)
class DemoDepartmentSpec:
    key: str
    name: str


@dataclass(frozen=True, slots=True)
class DemoUserSpec:
    email: str
    display_name: str
    role: UserRole
    department_key: str


@dataclass(frozen=True, slots=True)
class DemoIdentitySeedResult:
    departments: tuple[Department, ...]
    users: tuple[User, ...]
    created: int
    updated: int
    unchanged: int


DEMO_DEPARTMENTS = (
    DemoDepartmentSpec(key="engineering", name="Engineering"),
    DemoDepartmentSpec(key="operations", name="Operations"),
)

DEMO_USERS = (
    DemoUserSpec(
        email=DEMO_EMAIL,
        display_name="Demo Engineer",
        role=UserRole.EMPLOYEE,
        department_key="engineering",
    ),
    DemoUserSpec(
        email="employee.engineering.second@example.com",
        display_name="Demo Engineer Two",
        role=UserRole.EMPLOYEE,
        department_key="engineering",
    ),
    DemoUserSpec(
        email="employee.operations@example.com",
        display_name="Demo Operations Employee",
        role=UserRole.EMPLOYEE,
        department_key="operations",
    ),
    DemoUserSpec(
        email="it.engineering@example.com",
        display_name="Demo Engineering IT",
        role=UserRole.IT,
        department_key="engineering",
    ),
    DemoUserSpec(
        email="it.operations@example.com",
        display_name="Demo Operations IT",
        role=UserRole.IT,
        department_key="operations",
    ),
    DemoUserSpec(
        email="admin@example.com",
        display_name="Demo Administrator",
        role=UserRole.ADMIN,
        department_key="operations",
    ),
)

SeedAction = Literal["created", "updated", "unchanged"]
_STABLE_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")


def validate_demo_identity_specs(
    departments: Sequence[DemoDepartmentSpec] = DEMO_DEPARTMENTS,
    users: Sequence[DemoUserSpec] = DEMO_USERS,
) -> None:
    """Validate stable identities and references before any database write."""

    department_keys: set[str] = set()
    for department in departments:
        if not _STABLE_KEY_PATTERN.fullmatch(department.key):
            raise ValueError(f"Invalid demo department key: {department.key}")
        if department.key in department_keys:
            raise ValueError(f"Duplicate demo department key: {department.key}")
        if (
            department.name != " ".join(department.name.strip().split())
            or not 2 <= len(department.name) <= 80
        ):
            raise ValueError(f"Invalid demo department name: {department.name!r}")
        department_keys.add(department.key)

    emails: set[str] = set()
    for user in users:
        normalized_email = user.email.strip().casefold()
        if normalized_email != user.email or "@" not in user.email:
            raise ValueError(f"Invalid demo user email: {user.email!r}")
        if user.email in emails:
            raise ValueError(f"Duplicate demo user email: {user.email}")
        if user.department_key not in department_keys:
            raise ValueError(f"Unknown demo user department: {user.department_key}")
        if (
            user.display_name != " ".join(user.display_name.strip().split())
            or not 2 <= len(user.display_name) <= 120
        ):
            raise ValueError(f"Invalid demo user display name: {user.email}")
        emails.add(user.email)


def _password_matches(password: str, password_hash: str) -> bool:
    try:
        return verify_password(password, password_hash)
    except Exception:
        return False


async def _ensure_department(
    session: AsyncSession,
    spec: DemoDepartmentSpec,
) -> tuple[Department, SeedAction]:
    department = await session.scalar(select(Department).where(Department.key == spec.key))
    if department is None:
        department = Department(key=spec.key, name=spec.name)
        session.add(department)
        await session.flush()
        return department, "created"
    if department.name != spec.name:
        department.name = spec.name
        await session.flush()
        return department, "updated"
    return department, "unchanged"


async def _ensure_user(
    session: AsyncSession,
    *,
    spec: DemoUserSpec,
    department: Department,
    password: str,
) -> tuple[User, SeedAction]:
    repository = UserRepository()
    user = await repository.get_by_email(session, spec.email)
    if user is None:
        user = User(
            email=spec.email,
            display_name=spec.display_name,
            password_hash=hash_password(password),
            role=spec.role,
            department_id=department.id,
            active=True,
            memory_enabled=False,
            memory_epoch=0,
        )
        repository.add(session, user)
        await session.flush()
        return user, "created"

    changed = False
    desired = {
        "display_name": spec.display_name,
        "role": spec.role,
        "department_id": department.id,
        "active": True,
    }
    for attribute, value in desired.items():
        if getattr(user, attribute) != value:
            setattr(user, attribute, value)
            changed = True
    if not _password_matches(password, user.password_hash):
        user.password_hash = hash_password(password)
        changed = True
    if changed:
        await session.flush()
        return user, "updated"
    return user, "unchanged"


async def ensure_demo_accounts(
    session: AsyncSession,
    *,
    password: str,
) -> DemoIdentitySeedResult:
    """Converge the two departments and six accounts without duplicating records."""

    validate_demo_identity_specs()
    validate_password(password)
    counts: dict[SeedAction, int] = {"created": 0, "updated": 0, "unchanged": 0}
    departments: dict[str, Department] = {}
    for department_spec in DEMO_DEPARTMENTS:
        department, action = await _ensure_department(session, department_spec)
        departments[department_spec.key] = department
        counts[action] += 1

    users: list[User] = []
    for user_spec in DEMO_USERS:
        user, action = await _ensure_user(
            session,
            spec=user_spec,
            department=departments[user_spec.department_key],
            password=password,
        )
        users.append(user)
        counts[action] += 1

    return DemoIdentitySeedResult(
        departments=tuple(departments[department_spec.key] for department_spec in DEMO_DEPARTMENTS),
        users=tuple(users),
        created=counts["created"],
        updated=counts["updated"],
        unchanged=counts["unchanged"],
    )


async def ensure_demo_identity(session: AsyncSession, *, password: str) -> User:
    """Keep the narrow test fixture used by existing feature integration tests."""

    validate_password(password)
    department, _ = await _ensure_department(
        session,
        next(spec for spec in DEMO_DEPARTMENTS if spec.key == DEMO_DEPARTMENT_KEY),
    )
    user, _ = await _ensure_user(
        session,
        spec=next(spec for spec in DEMO_USERS if spec.email == DEMO_EMAIL),
        department=department,
        password=password,
    )
    return user
