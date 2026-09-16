"""Business reads behind the internal MCP boundary."""

from __future__ import annotations

from app.db import Database
from app.mcp_server.context import ExecutionContext, load_current_principal
from app.mcp_server.schemas import OpenTicketsResult, ServiceStatusResult, TicketSummary
from app.services.service_status import ServiceStatusService
from app.services.tickets import TicketReadService


async def check_service_status(
    database: Database, *, context: ExecutionContext, service_id: str
) -> ServiceStatusResult:
    await load_current_principal(database, context=context)
    async with database.session() as session:
        item = await ServiceStatusService().get(session, service_id=service_id)
    return ServiceStatusResult.model_validate(item, from_attributes=True)


async def get_my_open_tickets(
    database: Database, *, context: ExecutionContext
) -> OpenTicketsResult:
    principal = await load_current_principal(database, context=context)
    async with database.session() as session:
        tickets = await TicketReadService().list_my_open(session, principal=principal)
    return OpenTicketsResult(
        tickets=[TicketSummary.model_validate(ticket, from_attributes=True) for ticket in tickets]
    )
