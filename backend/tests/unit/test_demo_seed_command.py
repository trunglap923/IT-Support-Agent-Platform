from __future__ import annotations

from dataclasses import replace

import pytest

from app.auth.demo_identity import (
    DEMO_DEPARTMENTS,
    DEMO_USERS,
    validate_demo_identity_specs,
)
from app.demo_seed_command import DemoSeedReport, SeedCounts, build_parser, format_demo_seed_report


def test_identity_validation_rejects_duplicate_and_unknown_references() -> None:
    with pytest.raises(ValueError, match="Duplicate demo department key"):
        validate_demo_identity_specs((*DEMO_DEPARTMENTS, DEMO_DEPARTMENTS[0]), DEMO_USERS)

    unknown = replace(DEMO_USERS[0], department_key="missing")
    with pytest.raises(ValueError, match="Unknown demo user department"):
        validate_demo_identity_specs(DEMO_DEPARTMENTS, (unknown, *DEMO_USERS[1:]))


def test_seed_cli_only_exposes_non_destructive_dry_run() -> None:
    assert build_parser().parse_args([]).dry_run is False
    assert build_parser().parse_args(["--dry-run"]).dry_run is True
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--reset"])


def test_seed_summary_is_stable_and_explicit_about_dry_run() -> None:
    report = DemoSeedReport(
        dry_run=True,
        identities=SeedCounts(1, 2, 5),
        assets=SeedCounts(0, 0, 6),
        tickets=SeedCounts(0, 1, 17),
        knowledge=SeedCounts(2, 0, 9),
        documents=9,
        document_versions=11,
        chunks=None,
    )

    output = format_demo_seed_report(report)

    assert "Demo seed dry-run validated." in output
    assert "total              3        3         37     43" in output
    assert "documents=9 versions=11 chunks=not-written" in output
    assert "No database or document-storage changes were persisted." in output
