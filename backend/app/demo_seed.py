"""Validated, idempotent seed data for the standalone portfolio demo."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.demo_identity import DEMO_EMAIL, DEMO_USERS
from app.db.models import ServiceFaultMode, ServiceHealth, ServiceState, User, UserDevice
from app.services.service_status import SERVICE_IDS

SeedAction = Literal["created", "updated", "unchanged"]
_STABLE_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_DEVICE_PLATFORMS = frozenset({"windows", "macos", "linux", "other"})
_SERVICE_STATUSES = frozenset(item.value for item in ServiceHealth)
_SERVICE_FAULT_MODES = frozenset(item.value for item in ServiceFaultMode)


@dataclass(frozen=True, slots=True)
class DemoDeviceSpec:
    key: str
    owner_email: str
    label: str
    platform: str


@dataclass(frozen=True, slots=True)
class DemoServiceStateSpec:
    service_id: str
    status: str
    message: str
    fault_mode: str = ServiceFaultMode.NONE.value


@dataclass(frozen=True, slots=True)
class DemoAssetSeedResult:
    devices: tuple[UserDevice, ...]
    service_states: tuple[ServiceState, ...]
    created: int
    updated: int
    unchanged: int


DEMO_DEVICES = (
    DemoDeviceSpec(
        key="engineering-ubuntu-workstation",
        owner_email=DEMO_EMAIL,
        label="Engineering Ubuntu Workstation",
        platform="linux",
    ),
    DemoDeviceSpec(
        key="engineering-windows-laptop",
        owner_email=DEMO_EMAIL,
        label="Engineering Windows Laptop",
        platform="windows",
    ),
    DemoDeviceSpec(
        key="operations-windows-laptop",
        owner_email="employee.operations@example.com",
        label="Operations Windows Laptop",
        platform="windows",
    ),
)

DEMO_SERVICE_STATES = (
    DemoServiceStateSpec(
        service_id="vpn",
        status=ServiceHealth.HEALTHY.value,
        message="VPN gateway is operating normally.",
    ),
    DemoServiceStateSpec(
        service_id="registry",
        status=ServiceHealth.HEALTHY.value,
        message="Docker Registry is operating normally.",
    ),
    DemoServiceStateSpec(
        service_id="gitlab",
        status=ServiceHealth.HEALTHY.value,
        message="GitLab is operating normally.",
    ),
)


def validate_demo_asset_specs(
    devices: Sequence[DemoDeviceSpec] = DEMO_DEVICES,
    service_states: Sequence[DemoServiceStateSpec] = DEMO_SERVICE_STATES,
) -> None:
    """Validate deterministic keys and cross-references before writing anything."""

    known_emails = {spec.email for spec in DEMO_USERS}
    device_keys: set[str] = set()
    device_natural_keys: set[tuple[str, str]] = set()
    for spec in devices:
        if not _STABLE_KEY_PATTERN.fullmatch(spec.key):
            raise ValueError(f"Invalid device key: {spec.key}")
        if spec.key in device_keys:
            raise ValueError(f"Duplicate device key: {spec.key}")
        device_keys.add(spec.key)
        if spec.owner_email not in known_emails:
            raise ValueError(f"Unknown demo device owner: {spec.owner_email}")
        if spec.platform not in _DEVICE_PLATFORMS:
            raise ValueError(f"Unsupported device platform: {spec.platform}")
        if spec.label != " ".join(spec.label.strip().split()) or not 1 <= len(spec.label) <= 80:
            raise ValueError(f"Invalid device label: {spec.label!r}")
        natural_key = (spec.owner_email, spec.label.casefold())
        if natural_key in device_natural_keys:
            raise ValueError(f"Duplicate device label for owner: {spec.owner_email}/{spec.label}")
        device_natural_keys.add(natural_key)

    actual_service_ids = {spec.service_id for spec in service_states}
    if len(actual_service_ids) != len(service_states):
        raise ValueError("Duplicate service ID in demo seed")
    if actual_service_ids != SERVICE_IDS:
        raise ValueError("Demo service IDs must be exactly: " + ", ".join(sorted(SERVICE_IDS)))
    for service_spec in service_states:
        if service_spec.status not in _SERVICE_STATUSES:
            raise ValueError(f"Unsupported service status: {service_spec.status}")
        if service_spec.fault_mode not in _SERVICE_FAULT_MODES:
            raise ValueError(f"Unsupported service fault mode: {service_spec.fault_mode}")
        if (
            service_spec.message != service_spec.message.strip()
            or not 3 <= len(service_spec.message) <= 500
        ):
            raise ValueError(f"Invalid service message for: {service_spec.service_id}")


async def _ensure_device(
    session: AsyncSession,
    *,
    spec: DemoDeviceSpec,
    owner: User,
) -> tuple[UserDevice, SeedAction]:
    device = await session.scalar(
        select(UserDevice).where(
            UserDevice.owner_id == owner.id,
            UserDevice.label == spec.label,
        )
    )
    if device is None:
        device = UserDevice(
            owner_id=owner.id,
            label=spec.label,
            platform=spec.platform,
            active=True,
            version=1,
        )
        session.add(device)
        await session.flush()
        return device, "created"

    changed = False
    if device.platform != spec.platform:
        device.platform = spec.platform
        changed = True
    if not device.active:
        device.active = True
        changed = True
    if changed:
        device.version += 1
        await session.flush()
        return device, "updated"
    return device, "unchanged"


async def _ensure_service_state(
    session: AsyncSession,
    spec: DemoServiceStateSpec,
) -> tuple[ServiceState, SeedAction]:
    state = await session.get(ServiceState, spec.service_id)
    if state is None:
        state = ServiceState(
            service_id=spec.service_id,
            status=spec.status,
            message=spec.message,
            fault_mode=spec.fault_mode,
            updated_by=None,
        )
        session.add(state)
        await session.flush()
        return state, "created"

    changed = False
    desired = {
        "status": spec.status,
        "message": spec.message,
        "fault_mode": spec.fault_mode,
        "updated_by": None,
    }
    for attribute, value in desired.items():
        if getattr(state, attribute) != value:
            setattr(state, attribute, value)
            changed = True
    if changed:
        await session.flush()
        return state, "updated"
    return state, "unchanged"


async def ensure_demo_devices_and_service_states(
    session: AsyncSession,
    *,
    devices: Sequence[DemoDeviceSpec] = DEMO_DEVICES,
    service_states: Sequence[DemoServiceStateSpec] = DEMO_SERVICE_STATES,
) -> DemoAssetSeedResult:
    """Converge demo devices and service states after identities have been seeded."""

    validate_demo_asset_specs(devices, service_states)
    owner_emails = {spec.owner_email for spec in devices}
    owners = {
        user.email: user
        for user in await session.scalars(select(User).where(User.email.in_(owner_emails)))
    }
    missing_owners = owner_emails - owners.keys()
    if missing_owners:
        raise ValueError("Demo users must be seeded first: " + ", ".join(sorted(missing_owners)))

    counts: dict[SeedAction, int] = {"created": 0, "updated": 0, "unchanged": 0}
    seeded_devices: list[UserDevice] = []
    for spec in devices:
        device, action = await _ensure_device(session, spec=spec, owner=owners[spec.owner_email])
        seeded_devices.append(device)
        counts[action] += 1

    seeded_service_states: list[ServiceState] = []
    for service_spec in service_states:
        state, action = await _ensure_service_state(session, service_spec)
        seeded_service_states.append(state)
        counts[action] += 1

    return DemoAssetSeedResult(
        devices=tuple(seeded_devices),
        service_states=tuple(seeded_service_states),
        created=counts["created"],
        updated=counts["updated"],
        unchanged=counts["unchanged"],
    )
