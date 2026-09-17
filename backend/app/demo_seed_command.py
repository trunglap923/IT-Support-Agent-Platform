"""Validated, non-destructive command for the complete standalone demo seed."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.auth.demo_identity import (
    DEMO_DEPARTMENTS,
    DEMO_USERS,
    ensure_demo_accounts,
    validate_demo_identity_specs,
)
from app.auth.passwords import validate_password
from app.config import Settings
from app.db import Database
from app.demo_document_seed import (
    DemoKnowledgeSeedPlan,
    load_demo_corpus,
    plan_published_knowledge,
    seed_published_knowledge,
)
from app.demo_seed import (
    DEMO_DEVICES,
    DEMO_SERVICE_STATES,
    ensure_demo_devices_and_service_states,
    validate_demo_asset_specs,
)
from app.demo_ticket_seed import (
    DEMO_TICKETS,
    ensure_demo_tickets,
    validate_demo_ticket_specs,
)


class SeedResult(Protocol):
    @property
    def created(self) -> int: ...

    @property
    def updated(self) -> int: ...

    @property
    def unchanged(self) -> int: ...


@dataclass(frozen=True, slots=True)
class SeedCounts:
    created: int
    updated: int
    unchanged: int

    @property
    def total(self) -> int:
        return self.created + self.updated + self.unchanged

    @classmethod
    def from_result(cls, result: SeedResult) -> SeedCounts:
        return cls(
            created=result.created,
            updated=result.updated,
            unchanged=result.unchanged,
        )


@dataclass(frozen=True, slots=True)
class DemoSeedReport:
    dry_run: bool
    identities: SeedCounts
    assets: SeedCounts
    tickets: SeedCounts
    knowledge: SeedCounts
    documents: int
    document_versions: int
    chunks: int | None

    @property
    def total(self) -> SeedCounts:
        sections = (self.identities, self.assets, self.tickets, self.knowledge)
        return SeedCounts(
            created=sum(section.created for section in sections),
            updated=sum(section.updated for section in sections),
            unchanged=sum(section.unchanged for section in sections),
        )


def validate_demo_seed_inputs(*, password: str, data_root: Path) -> None:
    """Run all static and cross-reference validation before opening a write transaction."""

    validate_password(password)
    validate_demo_identity_specs()
    validate_demo_asset_specs()
    validate_demo_ticket_specs()
    load_demo_corpus(data_root)


async def _run_relational_seed(
    database: Database,
    *,
    password: str,
    dry_run: bool,
) -> tuple[SeedCounts, SeedCounts, SeedCounts]:
    async with database.session() as session:
        transaction = await session.begin()
        try:
            identities = await ensure_demo_accounts(session, password=password)
            assets = await ensure_demo_devices_and_service_states(session)
            tickets = await ensure_demo_tickets(session)
            counts = (
                SeedCounts.from_result(identities),
                SeedCounts.from_result(assets),
                SeedCounts.from_result(tickets),
            )
            if dry_run:
                await transaction.rollback()
            else:
                await transaction.commit()
            return counts
        except BaseException:
            if transaction.is_active:
                await transaction.rollback()
            raise


def _knowledge_counts(plan: DemoKnowledgeSeedPlan) -> SeedCounts:
    return SeedCounts(plan.created, plan.updated, plan.unchanged)


def _validate_converged_report(report: DemoSeedReport) -> None:
    expected = {
        "identities": len(DEMO_DEPARTMENTS) + len(DEMO_USERS),
        "assets": len(DEMO_DEVICES) + len(DEMO_SERVICE_STATES),
        "tickets": len(DEMO_TICKETS),
        "knowledge": report.document_versions,
    }
    for name, total in expected.items():
        actual = getattr(report, name).total
        if actual != total:
            raise RuntimeError(f"Demo seed summary mismatch for {name}: {actual} != {total}")


async def run_demo_seed(
    database: Database,
    *,
    password: str,
    data_root: Path,
    storage_root: Path,
    dry_run: bool = False,
) -> DemoSeedReport:
    """Validate and converge every demo fixture, or report the changes without persisting them."""

    validate_demo_seed_inputs(password=password, data_root=data_root)
    identities, assets, tickets = await _run_relational_seed(
        database,
        password=password,
        dry_run=dry_run,
    )
    knowledge_plan = await plan_published_knowledge(database, data_root=data_root)

    chunks: int | None = None
    if not dry_run:
        knowledge_result = await seed_published_knowledge(
            database,
            data_root=data_root,
            storage_root=storage_root,
        )
        chunks = knowledge_result.chunk_count
        converged = await plan_published_knowledge(database, data_root=data_root)
        if converged.created or converged.updated or converged.unchanged != converged.version_count:
            raise RuntimeError("Demo knowledge seed did not converge after apply")

    report = DemoSeedReport(
        dry_run=dry_run,
        identities=identities,
        assets=assets,
        tickets=tickets,
        knowledge=_knowledge_counts(knowledge_plan),
        documents=knowledge_plan.document_count,
        document_versions=knowledge_plan.version_count,
        chunks=chunks,
    )
    _validate_converged_report(report)
    return report


def format_demo_seed_report(report: DemoSeedReport) -> str:
    """Render one stable, grep-friendly summary for humans and CI logs."""

    rows = (
        ("identities", report.identities),
        ("assets", report.assets),
        ("tickets", report.tickets),
        ("knowledge", report.knowledge),
        ("total", report.total),
    )
    lines = [
        f"Demo seed {'dry-run' if report.dry_run else 'apply'} validated.",
        "section      created  updated  unchanged  total",
    ]
    lines.extend(
        f"{name:<12} {counts.created:>7}  {counts.updated:>7}  "
        f"{counts.unchanged:>9}  {counts.total:>5}"
        for name, counts in rows
    )
    chunk_value = "not-written" if report.chunks is None else str(report.chunks)
    lines.append(
        "knowledge    "
        f"documents={report.documents} versions={report.document_versions} chunks={chunk_value}"
    )
    if report.dry_run:
        lines.append("No database or document-storage changes were persisted.")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and seed the complete local demo without deleting existing data."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and show the planned summary without persisting database/storage changes",
    )
    return parser


async def async_main(*, dry_run: bool = False) -> None:
    settings = Settings()
    if settings.database_url is None:
        raise SystemExit("DATABASE_URL is required")
    if settings.demo_seed_password is None:
        raise SystemExit("DEMO_SEED_PASSWORD is required")

    database = Database(settings.database_url.get_secret_value())
    try:
        report = await run_demo_seed(
            database,
            password=settings.demo_seed_password.get_secret_value(),
            data_root=Path(settings.demo_corpus_path),
            storage_root=Path(settings.document_storage_path),
            dry_run=dry_run,
        )
        print(format_demo_seed_report(report))
    finally:
        await database.close()


def main() -> None:
    arguments = build_parser().parse_args()
    asyncio.run(async_main(dry_run=arguments.dry_run))


if __name__ == "__main__":
    main()
