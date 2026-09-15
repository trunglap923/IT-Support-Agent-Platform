"""Seed the minimal demo login account using secrets supplied at runtime."""

from __future__ import annotations

import asyncio

from app.auth.demo_identity import ensure_demo_identity
from app.config import Settings
from app.db import Database


async def async_main() -> None:
    settings = Settings()
    if settings.database_url is None:
        raise SystemExit("DATABASE_URL is required")
    if settings.demo_seed_password is None:
        raise SystemExit("DEMO_SEED_PASSWORD is required")

    database = Database(settings.database_url.get_secret_value())
    try:
        async with database.session() as session, session.begin():
            user = await ensure_demo_identity(
                session,
                password=settings.demo_seed_password.get_secret_value(),
            )
        print(f"Demo identity ready: {user.email}")
    finally:
        await database.close()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
