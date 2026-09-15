from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def sync_url(value: str) -> URL:
    return make_url(value).set(drivername="postgresql+psycopg")


@pytest.fixture
def migrated_database_url() -> Iterator[str]:
    configured_url = os.getenv("TEST_DATABASE_ADMIN_URL") or os.getenv("MIGRATION_DATABASE_URL")
    if not configured_url:
        if os.getenv("REQUIRE_DATABASE_TESTS") == "1":
            pytest.fail(
                "Set TEST_DATABASE_ADMIN_URL (or MIGRATION_DATABASE_URL) before the required "
                "database integration gate"
            )
        pytest.skip("TEST_DATABASE_ADMIN_URL is not configured")

    admin_url = sync_url(configured_url).set(database="postgres")
    database_name = f"test_app_{uuid4().hex}"
    target_url = admin_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))

        environment = os.environ.copy()
        environment["MIGRATION_DATABASE_URL"] = target_url.render_as_string(hide_password=False)
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=BACKEND_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        yield target_url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    finally:
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        admin_engine.dispose()
