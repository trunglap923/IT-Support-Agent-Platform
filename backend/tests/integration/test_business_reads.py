from __future__ import annotations

import asyncio
from uuid import uuid4

from app.auth.passwords import hash_password
from app.auth.principal import Principal
from app.db import Database
from app.db.models import Department, Ticket, User, UserRole
from app.services.service_status import ServiceStatusNotFoundError, ServiceStatusService
from app.services.tickets import TicketReadService


def test_service_allowlist_and_ticket_scope(migrated_database_url: str) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                engineering = Department(key="engineering", name="Engineering")
                finance = Department(key="finance", name="Finance")
                session.add_all([engineering, finance])
                await session.flush()
                employee = User(
                    email="reader@example.com",
                    display_name="Reader",
                    password_hash=hash_password("test-password"),
                    role=UserRole.EMPLOYEE,
                    department_id=engineering.id,
                    active=True,
                )
                coworker = User(
                    email="coworker@example.com",
                    display_name="Coworker",
                    password_hash=hash_password("test-password"),
                    role=UserRole.EMPLOYEE,
                    department_id=engineering.id,
                    active=True,
                )
                outsider = User(
                    email="finance@example.com",
                    display_name="Finance",
                    password_hash=hash_password("test-password"),
                    role=UserRole.EMPLOYEE,
                    department_id=finance.id,
                    active=True,
                )
                session.add_all([employee, coworker, outsider])
                await session.flush()
                session.add_all(
                    [
                        Ticket(
                            display_key="IT-0001",
                            owner_id=employee.id,
                            department_id=engineering.id,
                            title="VPN unavailable",
                            description="VPN connection fails during sign in.",
                            issue_type="vpn",
                            severity="normal",
                            status="open",
                        ),
                        Ticket(
                            display_key="IT-0002",
                            owner_id=coworker.id,
                            department_id=engineering.id,
                            title="Docker registry",
                            description="Registry authentication is unavailable.",
                            issue_type="docker",
                            severity="high",
                            status="in_progress",
                        ),
                        Ticket(
                            display_key="IT-0003",
                            owner_id=outsider.id,
                            department_id=finance.id,
                            title="GitLab access",
                            description="GitLab project cannot be opened.",
                            issue_type="gitlab",
                            severity="low",
                            status="open",
                        ),
                    ]
                )
                await ServiceStatusService().ensure_defaults(session)
                employee_id = employee.id
                engineering_id = engineering.id
                finance_id = finance.id

            employee_principal = Principal(
                user_id=employee_id,
                session_id=uuid4(),
                email="reader@example.com",
                display_name="Reader",
                role=UserRole.EMPLOYEE,
                department_id=engineering_id,
                department_key="engineering",
            )
            it_principal = Principal(
                user_id=uuid4(),
                session_id=uuid4(),
                email="it@example.com",
                display_name="IT",
                role=UserRole.IT,
                department_id=engineering_id,
                department_key="engineering",
            )
            admin_principal = Principal(
                user_id=uuid4(),
                session_id=uuid4(),
                email="admin@example.com",
                display_name="Admin",
                role=UserRole.ADMIN,
                department_id=finance_id,
                department_key="finance",
            )
            async with database.session() as session:
                services = await ServiceStatusService().list(session)
                assert {item.service_id for item in services} == {"vpn", "registry", "gitlab"}
                try:
                    await ServiceStatusService().get(session, service_id="arbitrary-host")
                except ServiceStatusNotFoundError:
                    pass
                else:
                    raise AssertionError("Non-allowlisted service was accepted")
                reads = TicketReadService()
                assert [
                    ticket.display_key
                    for ticket in await reads.list_my_open(session, principal=employee_principal)
                ] == ["IT-0001"]
                assert {
                    ticket.display_key
                    for ticket in await reads.list_visible(session, principal=it_principal)
                } == {"IT-0001", "IT-0002"}
                assert len(await reads.list_visible(session, principal=admin_principal)) == 3
        finally:
            await database.close()

    asyncio.run(scenario())
