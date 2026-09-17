from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import func, select

from app.db import Database
from app.db.models import Department, Document, Ticket, User, UserDevice
from app.demo_seed_command import run_demo_seed


def _data_root() -> Path:
    container_path = Path("/workspace/data")
    if container_path.is_dir():
        return container_path
    return Path(__file__).resolve().parents[3] / "data"


def test_full_demo_seed_dry_run_is_read_only_then_apply_converges(
    migrated_database_url: str,
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        storage_root = tmp_path / "documents"
        try:
            planned = await run_demo_seed(
                database,
                password="complete-demo-seed-password",
                data_root=_data_root(),
                storage_root=storage_root,
                dry_run=True,
            )
            async with database.session() as session:
                empty_counts = [
                    int(await session.scalar(select(func.count()).select_from(model)) or 0)
                    for model in (Department, User, UserDevice, Ticket, Document)
                ]

            assert planned.dry_run is True
            assert planned.identities.created == 8
            assert planned.assets.created == 6
            assert planned.tickets.created == 18
            assert planned.knowledge.created == 11
            assert planned.total.created == 43
            assert empty_counts == [0, 0, 0, 0, 0]
            assert not storage_root.exists()

            applied = await run_demo_seed(
                database,
                password="complete-demo-seed-password",
                data_root=_data_root(),
                storage_root=storage_root,
            )
            second_plan = await run_demo_seed(
                database,
                password="complete-demo-seed-password",
                data_root=_data_root(),
                storage_root=storage_root,
                dry_run=True,
            )

            assert applied.dry_run is False
            assert applied.total.created == 43
            assert applied.total.updated == applied.total.unchanged == 0
            assert applied.documents == 9
            assert applied.document_versions == 11
            assert applied.chunks == 41
            assert second_plan.total.created == second_plan.total.updated == 0
            assert second_plan.total.unchanged == 43
            assert second_plan.chunks is None
        finally:
            await database.close()

    asyncio.run(scenario())
