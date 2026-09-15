"""Idempotent minimal identity seed used before the full WP-04 dataset."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.db.models import Department, User, UserRole
from app.repositories.users import UserRepository

DEMO_EMAIL = "employee.engineering@example.com"
DEMO_DEPARTMENT_KEY = "engineering"


async def ensure_demo_identity(session: AsyncSession, *, password: str) -> User:
    department = await session.scalar(
        select(Department).where(Department.key == DEMO_DEPARTMENT_KEY)
    )
    if department is None:
        department = Department(key=DEMO_DEPARTMENT_KEY, name="Engineering")
        session.add(department)
        await session.flush()

    repository = UserRepository()
    user = await repository.get_by_email(session, DEMO_EMAIL)
    if user is not None:
        return user

    user = User(
        email=DEMO_EMAIL,
        display_name="Demo Engineer",
        password_hash=hash_password(password),
        role=UserRole.EMPLOYEE,
        department_id=department.id,
        active=True,
        memory_enabled=False,
        memory_epoch=0,
    )
    repository.add(session, user)
    await session.flush()
    return user
