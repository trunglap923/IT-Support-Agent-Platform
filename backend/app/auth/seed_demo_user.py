"""Seed validated demo identities, assets and ticket scenarios."""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.auth.demo_identity import DEMO_USERS, ensure_demo_accounts
from app.config import Settings
from app.db import Database
from app.demo_document_seed import seed_published_knowledge
from app.demo_seed import (
    DEMO_DEVICES,
    DEMO_SERVICE_STATES,
    ensure_demo_devices_and_service_states,
)
from app.demo_ticket_seed import DEMO_TICKETS, ensure_demo_tickets


async def async_main() -> None:
    settings = Settings()
    if settings.database_url is None:
        raise SystemExit("DATABASE_URL is required")
    if settings.demo_seed_password is None:
        raise SystemExit("DEMO_SEED_PASSWORD is required")

    database = Database(settings.database_url.get_secret_value())
    try:
        async with database.session() as session, session.begin():
            identity_result = await ensure_demo_accounts(
                session,
                password=settings.demo_seed_password.get_secret_value(),
            )
            asset_result = await ensure_demo_devices_and_service_states(session)
            ticket_result = await ensure_demo_tickets(session)
        knowledge_result = await seed_published_knowledge(
            database,
            data_root=Path(settings.demo_corpus_path),
            storage_root=Path(settings.document_storage_path),
        )
        print(
            "Demo identities ready: "
            f"created={identity_result.created}, updated={identity_result.updated}, "
            f"unchanged={identity_result.unchanged}"
        )
        for user_spec in DEMO_USERS:
            print(f"- {user_spec.email} ({user_spec.role.value}, {user_spec.department_key})")
        print(
            "Demo devices and service states ready: "
            f"created={asset_result.created}, updated={asset_result.updated}, "
            f"unchanged={asset_result.unchanged}"
        )
        for device_spec in DEMO_DEVICES:
            print(f"- device {device_spec.key} ({device_spec.owner_email}, {device_spec.platform})")
        for service_spec in DEMO_SERVICE_STATES:
            print(
                f"- service {service_spec.service_id} "
                f"({service_spec.status}, {service_spec.fault_mode})"
            )
        print(
            "Demo ticket scenarios ready: "
            f"created={ticket_result.created}, updated={ticket_result.updated}, "
            f"unchanged={ticket_result.unchanged}"
        )
        for status in ("open", "in_progress", "resolved"):
            count = sum(ticket.status == status for ticket in DEMO_TICKETS)
            print(f"- {status}: {count}")
        print(
            "Published knowledge ready: "
            f"documents={knowledge_result.document_count}, "
            f"versions={knowledge_result.version_count}, "
            f"chunks={knowledge_result.chunk_count}, "
            f"reused_jobs={knowledge_result.reused_jobs}"
        )
    finally:
        await database.close()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
