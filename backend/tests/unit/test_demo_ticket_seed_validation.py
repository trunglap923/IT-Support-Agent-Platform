from dataclasses import replace

import pytest

from app.demo_ticket_seed import DEMO_TICKETS, DemoTicketSpec, validate_demo_ticket_specs


def test_default_demo_ticket_specs_are_valid_and_balanced() -> None:
    validate_demo_ticket_specs()
    statuses = [ticket.status for ticket in DEMO_TICKETS]
    assert statuses.count("open") == 6
    assert statuses.count("in_progress") == 6
    assert statuses.count("resolved") == 6


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        (
            replace(DEMO_TICKETS[0], department_key="operations"),
            "department does not match owner",
        ),
        (
            replace(DEMO_TICKETS[0], device_key="operations-windows-laptop"),
            "device does not belong to owner",
        ),
        (
            replace(DEMO_TICKETS[4], resolution_note=None),
            "requires a resolution note",
        ),
        (
            replace(DEMO_TICKETS[0], resolution_note="Already fixed"),
            "Unresolved ticket cannot have",
        ),
    ],
)
def test_invalid_ticket_scope_and_state_are_rejected(
    replacement: DemoTicketSpec, message: str
) -> None:
    tickets = (replacement, *DEMO_TICKETS[1:])
    with pytest.raises(ValueError, match=message):
        validate_demo_ticket_specs(tickets)


def test_duplicate_ticket_key_is_rejected() -> None:
    duplicate = replace(DEMO_TICKETS[1], display_key=DEMO_TICKETS[0].display_key)
    with pytest.raises(ValueError, match="Duplicate demo ticket display key"):
        validate_demo_ticket_specs((DEMO_TICKETS[0], duplicate, *DEMO_TICKETS[2:]))
