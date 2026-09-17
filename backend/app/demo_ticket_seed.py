"""Validated, idempotent ticket scenarios for the standalone demo."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.demo_identity import DEMO_USERS
from app.db.models import (
    Department,
    Ticket,
    TicketIssueType,
    TicketSeverity,
    TicketStatus,
    User,
    UserDevice,
)
from app.demo_seed import DEMO_DEVICES

SeedAction = Literal["created", "updated", "unchanged"]
_DISPLAY_KEY_PATTERN = re.compile(r"^DEMO-[A-Z]{3}-[0-9]{3}$")
_ISSUE_TYPES = frozenset(item.value for item in TicketIssueType)
_SEVERITIES = frozenset(item.value for item in TicketSeverity)
_STATUSES = frozenset(item.value for item in TicketStatus)


@dataclass(frozen=True, slots=True)
class DemoTicketSpec:
    display_key: str
    owner_email: str
    department_key: str
    title: str
    description: str
    issue_type: str
    severity: str
    status: str
    device_key: str | None = None
    resolution_note: str | None = None


@dataclass(frozen=True, slots=True)
class DemoTicketSeedResult:
    tickets: tuple[Ticket, ...]
    created: int
    updated: int
    unchanged: int


DEMO_TICKETS = (
    DemoTicketSpec(
        "DEMO-ENG-001",
        "employee.engineering@example.com",
        "engineering",
        "VPN disconnects during remote work",
        "The VPN disconnects repeatedly after authentication from the Ubuntu workstation.",
        "vpn",
        "high",
        "open",
        "engineering-ubuntu-workstation",
    ),
    DemoTicketSpec(
        "DEMO-ENG-002",
        "employee.engineering@example.com",
        "engineering",
        "Docker Registry login rejected",
        "Docker login rejects the employee credentials from the Windows laptop.",
        "docker",
        "normal",
        "open",
        "engineering-windows-laptop",
    ),
    DemoTicketSpec(
        "DEMO-ENG-003",
        "employee.engineering@example.com",
        "engineering",
        "GitLab SSH key is not accepted",
        "GitLab rejects the configured SSH key while cloning an Engineering repository.",
        "gitlab",
        "normal",
        "in_progress",
        "engineering-ubuntu-workstation",
    ),
    DemoTicketSpec(
        "DEMO-ENG-004",
        "employee.engineering@example.com",
        "engineering",
        "Developer workstation clock drift",
        "The Windows workstation clock drifts and causes internal authentication failures.",
        "other",
        "low",
        "in_progress",
        "engineering-windows-laptop",
    ),
    DemoTicketSpec(
        "DEMO-ENG-005",
        "employee.engineering@example.com",
        "engineering",
        "VPN profile expired",
        "The Ubuntu workstation could not connect because its VPN profile had expired.",
        "vpn",
        "normal",
        "resolved",
        "engineering-ubuntu-workstation",
        "Issued a new VPN profile and verified a successful connection.",
    ),
    DemoTicketSpec(
        "DEMO-ENG-006",
        "employee.engineering@example.com",
        "engineering",
        "Docker token expired",
        "The Windows laptop could not pull images because its registry token had expired.",
        "docker",
        "high",
        "resolved",
        "engineering-windows-laptop",
        "Rotated the registry token and verified an authenticated image pull.",
    ),
    DemoTicketSpec(
        "DEMO-ENG-101",
        "employee.engineering.second@example.com",
        "engineering",
        "GitLab project access missing",
        "The second Engineering employee cannot open a project required for onboarding.",
        "gitlab",
        "normal",
        "open",
    ),
    DemoTicketSpec(
        "DEMO-ENG-102",
        "employee.engineering.second@example.com",
        "engineering",
        "VPN MFA prompt never arrives",
        "The VPN sign-in waits indefinitely for an MFA prompt that never arrives.",
        "vpn",
        "low",
        "open",
    ),
    DemoTicketSpec(
        "DEMO-ENG-103",
        "employee.engineering.second@example.com",
        "engineering",
        "Docker image pull is denied",
        "A required development image returns an authorization error during pull.",
        "docker",
        "high",
        "in_progress",
    ),
    DemoTicketSpec(
        "DEMO-ENG-104",
        "employee.engineering.second@example.com",
        "engineering",
        "Internal DNS lookup is intermittent",
        "Internal host names intermittently fail to resolve on the employee network.",
        "other",
        "normal",
        "in_progress",
    ),
    DemoTicketSpec(
        "DEMO-ENG-105",
        "employee.engineering.second@example.com",
        "engineering",
        "GitLab group membership stale",
        "The employee retained an outdated GitLab group membership after a team move.",
        "gitlab",
        "normal",
        "resolved",
        resolution_note="Synchronized group membership and confirmed repository access.",
    ),
    DemoTicketSpec(
        "DEMO-ENG-106",
        "employee.engineering.second@example.com",
        "engineering",
        "VPN route missing",
        "The VPN connected but did not install the route to Engineering services.",
        "vpn",
        "high",
        "resolved",
        resolution_note="Reinstalled the VPN profile and verified the Engineering route.",
    ),
    DemoTicketSpec(
        "DEMO-OPS-001",
        "employee.operations@example.com",
        "operations",
        "Operations VPN cannot connect",
        "The Operations Windows laptop reports a gateway timeout during VPN connection.",
        "vpn",
        "high",
        "open",
        "operations-windows-laptop",
    ),
    DemoTicketSpec(
        "DEMO-OPS-002",
        "employee.operations@example.com",
        "operations",
        "GitLab runbook repository unavailable",
        "The Operations employee cannot read the GitLab repository containing runbooks.",
        "gitlab",
        "normal",
        "open",
        "operations-windows-laptop",
    ),
    DemoTicketSpec(
        "DEMO-OPS-003",
        "employee.operations@example.com",
        "operations",
        "Registry image download is slow",
        "A deployment image download stalls from the Operations Windows laptop.",
        "docker",
        "high",
        "in_progress",
        "operations-windows-laptop",
    ),
    DemoTicketSpec(
        "DEMO-OPS-004",
        "employee.operations@example.com",
        "operations",
        "Operations printer mapping missing",
        "The shared printer mapping disappeared after a Windows profile update.",
        "other",
        "low",
        "in_progress",
        "operations-windows-laptop",
    ),
    DemoTicketSpec(
        "DEMO-OPS-005",
        "employee.operations@example.com",
        "operations",
        "VPN certificate renewal",
        "The Operations VPN certificate required renewal before the next shift.",
        "vpn",
        "normal",
        "resolved",
        "operations-windows-laptop",
        "Renewed the certificate and verified access to Operations systems.",
    ),
    DemoTicketSpec(
        "DEMO-OPS-006",
        "employee.operations@example.com",
        "operations",
        "GitLab runner permission denied",
        "A GitLab runner could not read an Operations deployment project.",
        "gitlab",
        "high",
        "resolved",
        "operations-windows-laptop",
        "Restored the runner role and verified a successful pipeline checkout.",
    ),
)


def validate_demo_ticket_specs(tickets: Sequence[DemoTicketSpec] = DEMO_TICKETS) -> None:
    """Validate ownership, department scope and ticket state invariants."""

    users = {spec.email: spec for spec in DEMO_USERS}
    devices = {spec.key: spec for spec in DEMO_DEVICES}
    display_keys: set[str] = set()
    status_counts: Counter[str] = Counter()
    departments: set[str] = set()
    owners: set[str] = set()

    for spec in tickets:
        if not _DISPLAY_KEY_PATTERN.fullmatch(spec.display_key):
            raise ValueError(f"Invalid demo ticket display key: {spec.display_key}")
        if spec.display_key in display_keys:
            raise ValueError(f"Duplicate demo ticket display key: {spec.display_key}")
        display_keys.add(spec.display_key)
        owner = users.get(spec.owner_email)
        if owner is None:
            raise ValueError(f"Unknown demo ticket owner: {spec.owner_email}")
        if owner.department_key != spec.department_key:
            raise ValueError(f"Ticket department does not match owner: {spec.display_key}")
        if spec.device_key is not None:
            device = devices.get(spec.device_key)
            if device is None:
                raise ValueError(f"Unknown demo ticket device: {spec.device_key}")
            if device.owner_email != spec.owner_email:
                raise ValueError(f"Ticket device does not belong to owner: {spec.display_key}")
        if spec.issue_type not in _ISSUE_TYPES:
            raise ValueError(f"Unsupported ticket issue type: {spec.issue_type}")
        if spec.severity not in _SEVERITIES:
            raise ValueError(f"Unsupported ticket severity: {spec.severity}")
        if spec.status not in _STATUSES:
            raise ValueError(f"Unsupported ticket status: {spec.status}")
        if not 3 <= len(spec.title.strip()) <= 160 or spec.title != spec.title.strip():
            raise ValueError(f"Invalid ticket title: {spec.display_key}")
        if (
            not 10 <= len(spec.description.strip()) <= 4000
            or spec.description != spec.description.strip()
        ):
            raise ValueError(f"Invalid ticket description: {spec.display_key}")
        if spec.status == TicketStatus.RESOLVED.value:
            if (
                spec.resolution_note is None
                or spec.resolution_note != spec.resolution_note.strip()
                or not 3 <= len(spec.resolution_note) <= 2000
            ):
                raise ValueError(f"Resolved ticket requires a resolution note: {spec.display_key}")
        elif spec.resolution_note is not None:
            raise ValueError(f"Unresolved ticket cannot have a resolution note: {spec.display_key}")
        status_counts[spec.status] += 1
        departments.add(spec.department_key)
        owners.add(spec.owner_email)

    if set(status_counts) != _STATUSES:
        raise ValueError("Demo tickets must cover open, in_progress and resolved")
    if len(departments) < 2:
        raise ValueError("Demo tickets must cover at least two departments")
    if len(owners) < 2:
        raise ValueError("Demo tickets must cover at least two owners")


async def _ensure_ticket(
    session: AsyncSession,
    *,
    spec: DemoTicketSpec,
    owner: User,
    department: Department,
    device: UserDevice | None,
) -> tuple[Ticket, SeedAction]:
    ticket = await session.scalar(select(Ticket).where(Ticket.display_key == spec.display_key))
    if ticket is None:
        ticket = Ticket(
            display_key=spec.display_key,
            owner_id=owner.id,
            department_id=department.id,
            device_id=device.id if device else None,
            conversation_id=None,
            approval_id=None,
            source="seed",
            title=spec.title,
            description=spec.description,
            issue_type=spec.issue_type,
            severity=spec.severity,
            status=spec.status,
            resolution_note=spec.resolution_note,
            version=1,
        )
        session.add(ticket)
        await session.flush()
        return ticket, "created"

    if ticket.source != "seed":
        raise ValueError(f"Demo ticket key collides with non-seed ticket: {spec.display_key}")
    changed = False
    desired = {
        "owner_id": owner.id,
        "department_id": department.id,
        "device_id": device.id if device else None,
        "conversation_id": None,
        "approval_id": None,
        "title": spec.title,
        "description": spec.description,
        "issue_type": spec.issue_type,
        "severity": spec.severity,
        "status": spec.status,
        "resolution_note": spec.resolution_note,
    }
    for attribute, value in desired.items():
        if getattr(ticket, attribute) != value:
            setattr(ticket, attribute, value)
            changed = True
    if changed:
        ticket.version += 1
        await session.flush()
        return ticket, "updated"
    return ticket, "unchanged"


async def ensure_demo_tickets(
    session: AsyncSession,
    *,
    tickets: Sequence[DemoTicketSpec] = DEMO_TICKETS,
) -> DemoTicketSeedResult:
    """Converge all ticket scenarios after identities and devices are seeded."""

    validate_demo_ticket_specs(tickets)
    owner_emails = {spec.owner_email for spec in tickets}
    department_keys = {spec.department_key for spec in tickets}
    owners = {
        user.email: user
        for user in await session.scalars(select(User).where(User.email.in_(owner_emails)))
    }
    departments = {
        department.key: department
        for department in await session.scalars(
            select(Department).where(Department.key.in_(department_keys))
        )
    }
    missing_owners = owner_emails - owners.keys()
    missing_departments = department_keys - departments.keys()
    if missing_owners:
        raise ValueError("Demo users must be seeded first: " + ", ".join(sorted(missing_owners)))
    if missing_departments:
        raise ValueError(
            "Demo departments must be seeded first: " + ", ".join(sorted(missing_departments))
        )
    for spec in tickets:
        if owners[spec.owner_email].department_id != departments[spec.department_key].id:
            raise ValueError(f"Stored ticket owner has the wrong department: {spec.display_key}")

    device_specs = {spec.key: spec for spec in DEMO_DEVICES}
    stored_devices = {
        (device.owner_id, device.label): device
        for device in await session.scalars(
            select(UserDevice).where(
                UserDevice.owner_id.in_([owner.id for owner in owners.values()])
            )
        )
    }
    devices: dict[str, UserDevice] = {}
    for device_key in {spec.device_key for spec in tickets if spec.device_key is not None}:
        device_spec = device_specs[device_key]
        natural_key = (owners[device_spec.owner_email].id, device_spec.label)
        device = stored_devices.get(natural_key)
        if device is None or not device.active:
            raise ValueError(f"Demo device must be seeded and active first: {device_key}")
        devices[device_key] = device

    counts: dict[SeedAction, int] = {"created": 0, "updated": 0, "unchanged": 0}
    seeded_tickets: list[Ticket] = []
    for spec in tickets:
        ticket, action = await _ensure_ticket(
            session,
            spec=spec,
            owner=owners[spec.owner_email],
            department=departments[spec.department_key],
            device=devices.get(spec.device_key) if spec.device_key else None,
        )
        seeded_tickets.append(ticket)
        counts[action] += 1

    return DemoTicketSeedResult(
        tickets=tuple(seeded_tickets),
        created=counts["created"],
        updated=counts["updated"],
        unchanged=counts["unchanged"],
    )
