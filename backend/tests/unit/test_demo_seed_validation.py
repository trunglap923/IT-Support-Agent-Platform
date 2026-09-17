from dataclasses import replace

import pytest

from app.demo_seed import (
    DEMO_DEVICES,
    DEMO_SERVICE_STATES,
    DemoDeviceSpec,
    validate_demo_asset_specs,
)


def test_default_demo_asset_specs_are_valid() -> None:
    validate_demo_asset_specs()


@pytest.mark.parametrize(
    ("devices", "message"),
    [
        (
            (*DEMO_DEVICES, replace(DEMO_DEVICES[0], key=DEMO_DEVICES[1].key)),
            "Duplicate device key",
        ),
        (
            (replace(DEMO_DEVICES[0], owner_email="missing@example.com"),),
            "Unknown demo device owner",
        ),
        (
            (replace(DEMO_DEVICES[0], platform="ubuntu"),),
            "Unsupported device platform",
        ),
    ],
)
def test_invalid_device_specs_are_rejected(
    devices: tuple[DemoDeviceSpec, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_demo_asset_specs(devices=devices)


def test_service_seed_requires_the_exact_allowlist() -> None:
    with pytest.raises(ValueError, match="must be exactly"):
        validate_demo_asset_specs(service_states=DEMO_SERVICE_STATES[:-1])


def test_invalid_service_state_is_rejected() -> None:
    invalid = replace(DEMO_SERVICE_STATES[0], status="operational")
    with pytest.raises(ValueError, match="Unsupported service status"):
        validate_demo_asset_specs(service_states=(invalid, *DEMO_SERVICE_STATES[1:]))
