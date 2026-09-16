"""Allowlisted reads and deterministic seed data for simulated service health."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServiceState

SERVICE_IDS = frozenset({"vpn", "registry", "gitlab"})
DEFAULT_SERVICE_STATES = {
    "vpn": ("healthy", "VPN gateway is operating normally."),
    "registry": ("healthy", "Container registry is operating normally."),
    "gitlab": ("healthy", "GitLab is operating normally."),
}


class ServiceStatusNotFoundError(LookupError):
    pass


class ServiceStatusService:
    async def ensure_defaults(self, session: AsyncSession) -> None:
        existing = set((await session.scalars(select(ServiceState.service_id))).all())
        for service_id, (health, message) in DEFAULT_SERVICE_STATES.items():
            if service_id not in existing:
                session.add(
                    ServiceState(
                        service_id=service_id,
                        status=health,
                        message=message,
                        fault_mode="none",
                    )
                )
        await session.flush()

    async def get(self, session: AsyncSession, *, service_id: str) -> ServiceState:
        normalized = service_id.strip().casefold()
        if normalized not in SERVICE_IDS:
            raise ServiceStatusNotFoundError("Service is not allowlisted")
        state = await session.get(ServiceState, normalized)
        if state is None:
            raise ServiceStatusNotFoundError("Service state was not found")
        return state

    async def list(self, session: AsyncSession) -> list[ServiceState]:
        statement = select(ServiceState).order_by(ServiceState.service_id)
        return list((await session.scalars(statement)).all())

    async def update(
        self,
        session: AsyncSession,
        *,
        service_id: str,
        status: str,
        message: str,
        fault_mode: str,
        updated_by: UUID,
    ) -> ServiceState:
        item = await self.get(session, service_id=service_id)
        item.status = status
        item.message = message.strip()
        item.fault_mode = fault_mode
        item.updated_by = updated_by
        await session.flush()
        return item
