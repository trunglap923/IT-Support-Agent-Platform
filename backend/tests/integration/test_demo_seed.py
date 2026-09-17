from __future__ import annotations

import asyncio

from sqlalchemy import func, select

from app.auth.demo_identity import ensure_demo_accounts
from app.db import Database
from app.db.models import ServiceState, User, UserDevice
from app.demo_seed import (
    DEMO_DEVICES,
    DEMO_SERVICE_STATES,
    ensure_demo_devices_and_service_states,
)


def test_demo_devices_and_service_states_are_idempotent(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_accounts(session, password="demo-assets-test-password")
                first = await ensure_demo_devices_and_service_states(session)
                first_device_ids = {device.label: device.id for device in first.devices}

            async with database.session() as session, session.begin():
                second = await ensure_demo_devices_and_service_states(session)
                devices = list(
                    (
                        await session.scalars(
                            select(UserDevice).order_by(UserDevice.label, UserDevice.id)
                        )
                    ).all()
                )
                services = list(
                    (
                        await session.scalars(
                            select(ServiceState).order_by(ServiceState.service_id)
                        )
                    ).all()
                )
                users_by_id = {user.id: user.email for user in await session.scalars(select(User))}
                device_count = await session.scalar(select(func.count()).select_from(UserDevice))
                service_count = await session.scalar(select(func.count()).select_from(ServiceState))

            assert first.created == 6
            assert first.updated == 0
            assert first.unchanged == 0
            assert second.created == 0
            assert second.updated == 0
            assert second.unchanged == 6
            assert device_count == len(DEMO_DEVICES) == 3
            assert service_count == len(DEMO_SERVICE_STATES) == 3
            assert {device.label: device.id for device in devices} == first_device_ids
            assert {
                (users_by_id[item.owner_id], item.label, item.platform) for item in devices
            } == {(spec.owner_email, spec.label, spec.platform) for spec in DEMO_DEVICES}
            engineering_platforms = {
                device.platform
                for device in devices
                if users_by_id[device.owner_id] == "employee.engineering@example.com"
            }
            assert engineering_platforms == {"linux", "windows"}
            assert all(device.active and device.version == 1 for device in devices)
            assert {
                (state.service_id, state.status, state.message, state.fault_mode)
                for state in services
            } == {
                (spec.service_id, spec.status, spec.message, spec.fault_mode)
                for spec in DEMO_SERVICE_STATES
            }
            assert all(state.updated_by is None for state in services)
        finally:
            await database.close()

    asyncio.run(scenario())


def test_demo_asset_seed_repairs_mutable_fields_without_duplication(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        try:
            async with database.session() as session, session.begin():
                await ensure_demo_accounts(session, password="demo-assets-test-password")
                first = await ensure_demo_devices_and_service_states(session)
                first.devices[0].platform = "other"
                first.devices[0].active = False
                first.service_states[0].status = "down"
                first.service_states[0].message = "Changed during demo."
                first_device_id = first.devices[0].id

            async with database.session() as session, session.begin():
                repaired = await ensure_demo_devices_and_service_states(session)
                device = await session.get(UserDevice, first_device_id)
                vpn = await session.get(ServiceState, "vpn")

            assert repaired.created == 0
            assert repaired.updated == 2
            assert repaired.unchanged == 4
            assert device is not None
            assert device.platform == "linux"
            assert device.active is True
            assert device.version == 2
            assert vpn is not None
            assert vpn.status == "healthy"
            assert vpn.message == "VPN gateway is operating normally."
        finally:
            await database.close()

    asyncio.run(scenario())
