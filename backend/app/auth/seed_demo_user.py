"""Seed demo departments and accounts using a runtime-supplied password."""

from __future__ import annotations

import asyncio

from app.auth.demo_identity import DEMO_USERS, ensure_demo_accounts
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
            result = await ensure_demo_accounts(
                session,
                password=settings.demo_seed_password.get_secret_value(),
            )
        print(
            "Demo identities ready: "
            f"created={result.created}, updated={result.updated}, "
            f"unchanged={result.unchanged}"
        )
        for spec in DEMO_USERS:
            print(f"- {spec.email} ({spec.role.value}, {spec.department_key})")
    finally:
        await database.close()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
