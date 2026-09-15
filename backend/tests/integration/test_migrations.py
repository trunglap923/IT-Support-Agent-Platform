from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def sync_url(value: str) -> URL:
    url = make_url(value)
    return url.set(drivername="postgresql+psycopg")


def test_alembic_upgrade_on_clean_database() -> None:
    configured_url = os.getenv("TEST_DATABASE_ADMIN_URL") or os.getenv("MIGRATION_DATABASE_URL")
    if not configured_url:
        if os.getenv("REQUIRE_DATABASE_TESTS") == "1":
            pytest.fail(
                "Set TEST_DATABASE_ADMIN_URL (or MIGRATION_DATABASE_URL) before the required "
                "database integration gate"
            )
        pytest.skip("TEST_DATABASE_ADMIN_URL is not configured")

    admin_url = sync_url(configured_url).set(database="postgres")
    database_name = f"test_migrations_{uuid4().hex}"
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

        target_engine = create_engine(target_url)
        try:
            with target_engine.connect() as connection:
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                vector_version = connection.execute(
                    text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                ).scalar_one()
            assert revision == "0004_conversation_runs"
            assert vector_version == "0.8.2"
        finally:
            target_engine.dispose()
    finally:
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        admin_engine.dispose()
