import asyncio

from sqlalchemy import func, select

from app.auth.demo_identity import DEMO_EMAIL, ensure_demo_identity
from app.auth.passwords import verify_password
from app.db import Database
from app.db.models import User, UserRole
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
                second = await ensure_demo_identity(
                    session, password="correct-horse-battery-staple"
                )
                count = await session.scalar(select(func.count()).select_from(User))
                found = await UserRepository().get_by_email(session, DEMO_EMAIL.upper())

            assert second.id == first_id
            assert count == 1
            assert found is not None
            assert found.role is UserRole.EMPLOYEE
            assert found.memory_enabled is False
            assert found.password_hash != "correct-horse-battery-staple"
            assert verify_password("correct-horse-battery-staple", found.password_hash)
        finally:
            await database.close()

    asyncio.run(scenario())
