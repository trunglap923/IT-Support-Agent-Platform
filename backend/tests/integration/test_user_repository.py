import asyncio

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.auth.demo_identity import (
    DEMO_EMAIL,
    DEMO_USERS,
    ensure_demo_accounts,
    ensure_demo_identity,
)
from app.auth.passwords import verify_password
from app.db import Database
from app.db.models import Department, User, UserRole
from app.repositories.users import UserRepository


def test_demo_identity_is_hashed_idempotent_and_queryable(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                first = await ensure_demo_identity(session, password="correct-horse-battery-staple")
                first_id = first.id

            async with database.session() as session, session.begin():
                second = await ensure_demo_identity(session, password="updated-demo-password")
                count = await session.scalar(select(func.count()).select_from(User))
                found = await UserRepository().get_by_email(session, DEMO_EMAIL.upper())

            assert second.id == first_id
            assert count == 1
            assert found is not None
            assert found.role is UserRole.EMPLOYEE
            assert found.memory_enabled is True
            assert found.password_hash != "correct-horse-battery-staple"
            assert verify_password("updated-demo-password", found.password_hash)
            assert not verify_password("correct-horse-battery-staple", found.password_hash)
        finally:
            await database.close()

    asyncio.run(scenario())


def test_full_demo_accounts_are_hashed_mapped_and_idempotent(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        password = "all-demo-accounts-password"
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                first = await ensure_demo_accounts(session, password=password)
                first_ids = {user.email: user.id for user in first.users}
                first_hashes = {user.email: user.password_hash for user in first.users}

            async with database.session() as session, session.begin():
                second = await ensure_demo_accounts(session, password=password)
                users = list(
                    (
                        await session.scalars(
                            select(User).options(joinedload(User.department)).order_by(User.email)
                        )
                    ).all()
                )
                department_count = await session.scalar(
                    select(func.count()).select_from(Department)
                )

            assert first.created == 8
            assert first.updated == 0
            assert first.unchanged == 0
            assert second.created == 0
            assert second.updated == 0
            assert second.unchanged == 8
            assert department_count == 2
            assert len(users) == 6
            assert {user.email: user.id for user in users} == first_ids
            assert {user.email: user.password_hash for user in users} == first_hashes
            assert all(user.password_hash != password for user in users)
            assert all(user.password_hash.startswith("$argon2") for user in users)
            assert all(verify_password(password, user.password_hash) for user in users)
            assert all(user.active for user in users)
            assert all(user.memory_enabled is True for user in users)

            expected = {spec.email: spec for spec in DEMO_USERS}
            assert {user.role for user in users} == {
                UserRole.EMPLOYEE,
                UserRole.IT,
                UserRole.ADMIN,
            }
            for user in users:
                spec = expected[user.email]
                assert user.role is spec.role
                assert user.department.key == spec.department_key
        finally:
            await database.close()

    asyncio.run(scenario())
