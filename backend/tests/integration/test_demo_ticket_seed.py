from __future__ import annotations

import asyncio
from collections import Counter
from uuid import uuid4

from sqlalchemy import func, select

from app.auth.demo_identity import ensure_demo_accounts
from app.auth.principal import Principal
from app.db import Database
from app.db.models import Department, Ticket, User, UserDevice
from app.demo_seed import ensure_demo_devices_and_service_states
from app.demo_ticket_seed import DEMO_TICKETS, ensure_demo_tickets
from app.services.tickets import TicketReadService


def test_demo_tickets_are_idempotent_and_keep_owner_scope(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_accounts(session, password="demo-ticket-test-password")
                await ensure_demo_devices_and_service_states(session)
                first = await ensure_demo_tickets(session)
                first_ids = {ticket.display_key: ticket.id for ticket in first.tickets}

            async with database.session() as session, session.begin():
                second = await ensure_demo_tickets(session)
                tickets = list(
                    (await session.scalars(select(Ticket).order_by(Ticket.display_key))).all()
                )
                users = {user.email: user for user in await session.scalars(select(User))}
                departments = {
                    department.id: department.key
                    for department in await session.scalars(select(Department))
                }
                devices = {
                    device.id: device for device in await session.scalars(select(UserDevice))
                }
                ticket_count = await session.scalar(select(func.count()).select_from(Ticket))

                def principal(email: str) -> Principal:
                    user = users[email]
                    return Principal(
                        user_id=user.id,
                        session_id=uuid4(),
                        email=user.email,
                        display_name=user.display_name,
                        role=user.role,
                        department_id=user.department_id,
                        department_key=departments[user.department_id],
                    )

                reads = TicketReadService()
                employee_visible = await reads.list_visible(
                    session,
                    principal=principal("employee.engineering@example.com"),
                )
                engineering_visible = await reads.list_visible(
                    session,
                    principal=principal("it.engineering@example.com"),
                )
                operations_visible = await reads.list_visible(
                    session,
                    principal=principal("it.operations@example.com"),
                )
                admin_visible = await reads.list_visible(
                    session,
                    principal=principal("admin@example.com"),
                )

            assert first.created == len(DEMO_TICKETS) == 18
            assert first.updated == 0
            assert first.unchanged == 0
            assert second.created == 0
            assert second.updated == 0
            assert second.unchanged == 18
            assert ticket_count == 18
            assert {ticket.display_key: ticket.id for ticket in tickets} == first_ids
            assert Counter(ticket.status for ticket in tickets) == {
                "open": 6,
                "in_progress": 6,
                "resolved": 6,
            }
            assert len(employee_visible) == 6
            assert {ticket.owner_id for ticket in employee_visible} == {
                users["employee.engineering@example.com"].id
            }
            assert len(engineering_visible) == 12
            assert {departments[ticket.department_id] for ticket in engineering_visible} == {
                "engineering"
            }
            assert len(operations_visible) == 6
            assert {departments[ticket.department_id] for ticket in operations_visible} == {
                "operations"
            }
            assert len(admin_visible) == 18
            assert all(
                departments[ticket.department_id]
                == next(
                    spec.department_key
                    for spec in DEMO_TICKETS
                    if spec.display_key == ticket.display_key
                )
                for ticket in tickets
            )
            assert all(
                ticket.device_id is None or devices[ticket.device_id].owner_id == ticket.owner_id
                for ticket in tickets
            )
            assert all(
                (ticket.resolution_note is not None) == (ticket.status == "resolved")
                for ticket in tickets
            )
            assert all(ticket.source == "seed" and ticket.version == 1 for ticket in tickets)
        finally:
            await database.close()

    asyncio.run(scenario())


def test_demo_ticket_seed_repairs_scenario_without_duplicate(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_accounts(session, password="demo-ticket-test-password")
                await ensure_demo_devices_and_service_states(session)
                first = await ensure_demo_tickets(session)
                target = first.tickets[0]
                target.status = "in_progress"
                target.severity = "low"
                target_id = target.id

            async with database.session() as session, session.begin():
                repaired = await ensure_demo_tickets(session)
                target = await session.get(Ticket, target_id)

            assert repaired.created == 0
            assert repaired.updated == 1
            assert repaired.unchanged == 17
            assert target is not None
            assert target.status == "open"
            assert target.severity == "high"
            assert target.version == 2
        finally:
            await database.close()

    asyncio.run(scenario())
