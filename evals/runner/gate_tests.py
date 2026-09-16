"""Run the database-backed release-gate regression suites and emit safe evidence."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.runner.report import git_revision

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
DEFAULT_OUTPUT = ROOT / "reports" / "runs" / "wp13-local-gates.json"

GATE_FILES = {
    "G-01": {
        "test_conversation_ownership",
        "test_cross_conversation_memory",
        "test_document_lifecycle",
        "test_feedback_api",
        "test_hybrid_retrieval",
        "test_sse_api",
    },
    "G-02": {"test_approval_lifecycle", "test_ticket_write"},
    "G-03": {"test_workflow_failure_recovery", "test_workflow_recovery"},
    "G-08-safety": {
        "test_consent_memory",
        "test_cross_conversation_memory",
        "test_memory_concurrency",
    },
}
TEST_FILES = sorted({name for names in GATE_FILES.values() for name in names})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def _module_name(classname: str) -> str:
    match = re.search(r"(test_[a-z0-9_]+)", classname)
    return match.group(1) if match else "unknown"


def _parse_junit(path: Path) -> list[dict[str, Any]]:
    root = ET.parse(path).getroot()
    cases: list[dict[str, Any]] = []
    for node in root.iter("testcase"):
        status = "passed"
        if node.find("failure") is not None:
            status = "failed"
        elif node.find("error") is not None:
            status = "error"
        elif node.find("skipped") is not None:
            status = "skipped"
        cases.append(
            {
                "test_id": f"{node.attrib.get('classname', '')}::{node.attrib.get('name', '')}",
                "module": _module_name(node.attrib.get("classname", "")),
                "status": status,
                "duration_seconds": round(float(node.attrib.get("time", "0")), 3),
            }
        )
    return cases


def main() -> None:
    args = parse_args()
    environment = os.environ.copy()
    environment["REQUIRE_DATABASE_TESTS"] = "1"
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="it-support-gates-") as directory:
        junit = Path(directory) / "junit.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            *[f"tests/integration/{name}.py" for name in TEST_FILES],
            "--junitxml",
            str(junit),
            "-q",
        ]
        completed = subprocess.run(
            command,
            cwd=BACKEND,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        cases = _parse_junit(junit) if junit.exists() else []

    suites: dict[str, dict[str, Any]] = {}
    for gate, modules in GATE_FILES.items():
        selected = [case for case in cases if case["module"] in modules]
        counts = {
            status: sum(case["status"] == status for case in selected)
            for status in ("passed", "failed", "error", "skipped")
        }
        suites[gate] = {
            "status": "pass"
            if selected and counts["failed"] == counts["error"] == counts["skipped"] == 0
            else "fail",
            "counts": counts,
            "test_ids": [case["test_id"] for case in selected],
        }

    artifact = {
        "schema_version": "gate-test-evidence-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_revision": git_revision(ROOT),
        "environment": "isolated PostgreSQL databases created per test",
        "duration_seconds": round(time.perf_counter() - started, 3),
        "pytest_exit_code": completed.returncode,
        "suites": suites,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    passed = sum(case["status"] == "passed" for case in cases)
    print(f"Gate regression evidence: {passed}/{len(cases)} passed; artifact={args.output}")
    if completed.returncode != 0:
        print(completed.stdout[-2_000:])
        print(completed.stderr[-2_000:])
        raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
