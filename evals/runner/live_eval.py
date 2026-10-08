"""Run the paid agent evaluation against a disposable PostgreSQL database."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
DEFAULT_POSTGRES_IMAGE = (
    "pgvector/pgvector:0.8.2-pg17-bookworm@"
    "sha256:feb68f4f15446397d8cac7f4fe48fe4586de83160d1fc48b46283312d1a33966"
)
DATABASE_NAME = "agent_live_eval"
DATABASE_USER = "eval_runner"
DATABASE_PASSWORD = "eval-only-local-password"


def _docker(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], check=True, text=True, capture_output=capture_output)


def _published_port(container_name: str) -> int:
    result = _docker("port", container_name, "5432/tcp", capture_output=True)
    mappings = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not mappings:
        raise RuntimeError("Docker did not publish the evaluation PostgreSQL port")
    try:
        return int(mappings[0].rsplit(":", 1)[1])
    except (IndexError, ValueError) as exc:
        raise RuntimeError(f"Unexpected Docker port mapping: {mappings[0]}") from exc


def _wait_until_ready(container_name: str) -> None:
    timeout = float(os.getenv("EVAL_DATABASE_START_TIMEOUT_SECONDS", "60"))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "pg_isready",
                "--username",
                DATABASE_USER,
                "--dbname",
                DATABASE_NAME,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError(f"Evaluation PostgreSQL was not ready within {timeout:g} seconds")


def _migrate(database_url: str) -> None:
    environment = os.environ.copy()
    environment["MIGRATION_DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
    )


def _evaluate(database_url: str) -> None:
    environment = os.environ.copy()
    environment["EVAL_DATABASE_URL"] = database_url
    subprocess.run(
        [
            sys.executable,
            "-m",
            "evals.runner.cli",
            "--mode",
            "live",
            "--split",
            "development",
            "--category",
            "rag",
            "--max-cases",
            "1",
            "--repetitions",
            "3",
            "--output",
            "reports/raw/agent-evaluation-live.json",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )


def main() -> None:
    if os.getenv("RUN_LIVE_EVAL") != "1":
        raise SystemExit("Live evaluation requires RUN_LIVE_EVAL=1")

    container_name = f"it-support-agent-live-eval-{uuid4().hex[:12]}"
    image = os.getenv("EVAL_POSTGRES_IMAGE", DEFAULT_POSTGRES_IMAGE)
    started = False
    try:
        _docker(
            "run",
            "--detach",
            "--rm",
            "--name",
            container_name,
            "--publish",
            "127.0.0.1::5432",
            "--env",
            f"POSTGRES_DB={DATABASE_NAME}",
            "--env",
            f"POSTGRES_USER={DATABASE_USER}",
            "--env",
            f"POSTGRES_PASSWORD={DATABASE_PASSWORD}",
            image,
        )
        started = True
        port = _published_port(container_name)
        _wait_until_ready(container_name)
        sync_url = (
            f"postgresql+psycopg://{DATABASE_USER}:{DATABASE_PASSWORD}"
            f"@127.0.0.1:{port}/{DATABASE_NAME}"
        )
        async_url = sync_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
        _migrate(sync_url)
        _evaluate(async_url)
    finally:
        if started:
            subprocess.run(
                ["docker", "rm", "--force", container_name],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


if __name__ == "__main__":
    main()
