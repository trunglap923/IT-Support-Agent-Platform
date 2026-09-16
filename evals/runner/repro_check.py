"""Prove that two fake evaluation runs produce the same scored result digest."""

from __future__ import annotations

import asyncio
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory

from evals.runner.cli import run


async def _check() -> None:
    with TemporaryDirectory(prefix="it-support-eval-") as directory:
        root = Path(directory)
        arguments = {
            "mode": "fake",
            "split": "development",
            "category": None,
            "max_cases": None,
            "repetitions": 2,
            "seed": 20260916,
        }
        first = await run(Namespace(**arguments, output=root / "first.json"))
        second = await run(Namespace(**arguments, output=root / "second.json"))
        if first["dataset_sha256"] != second["dataset_sha256"]:
            raise SystemExit("Dataset digest changed between identical fake runs")
        if first["result_digest"] != second["result_digest"]:
            raise SystemExit("Scored result changed between identical fake runs")
        print(
            "Reproducibility check passed: "
            f"{first['run_count']} runs, result_digest={first['result_digest']}"
        )


if __name__ == "__main__":
    asyncio.run(_check())
