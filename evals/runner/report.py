"""Build safe, reproducible evaluation artifacts."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.runner.harness import CaseRun


def git_revision(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return "unavailable-container-build"
    revision = completed.stdout.strip() or "unknown"
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return f"{revision}-dirty" if status.stdout.strip() else revision


def build_report(
    *,
    mode: str,
    model: str,
    split: str,
    seed: int,
    dataset_sha256: str,
    document_snapshots: list[str],
    run_configuration: dict[str, Any],
    runs: list[CaseRun],
    root: Path,
) -> dict[str, Any]:
    cases = [
        {
            "case_id": run.case_id,
            "repetition": run.repetition,
            "latency_ms": round(run.latency_ms, 3),
            "outcome": run.output.outcome,
            "citations": list(run.output.citations),
            "tool_sequence": list(run.output.tool_sequence),
            "db_changes": list(run.output.db_changes),
            "execution_backend": run.output.execution_backend,
            "provider_request_id": run.output.provider_request_id,
            "error_type": run.error_type,
            "input_tokens": run.output.input_tokens,
            "output_tokens": run.output.output_tokens,
            "scores": run.scores,
        }
        for run in runs
    ]
    stable_cases = [
        {key: value for key, value in item.items() if key != "latency_ms"} for item in cases
    ]
    stable = json.dumps(stable_cases, sort_keys=True, separators=(",", ":"))
    passed = sum(bool(item["scores"]["deterministic_pass"]) for item in cases)
    return {
        "report_version": "agent-eval-report-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_revision": git_revision(root),
        "mode": mode,
        "model": model,
        "split": split,
        "seed": seed,
        "dataset_sha256": dataset_sha256,
        "document_snapshots": sorted(set(document_snapshots)),
        "rubric_version": "agent-eval-v1",
        "prompt_version": "structured-support-v1",
        "run_configuration": run_configuration,
        "run_count": len(cases),
        "deterministic_pass": {"numerator": passed, "denominator": len(cases)},
        "result_digest": hashlib.sha256(stable.encode()).hexdigest(),
        "token_totals": {
            "input": sum(item["input_tokens"] for item in cases),
            "output": sum(item["output_tokens"] for item in cases),
        },
        "limitations": [
            "Fake mode validates the harness and policy contracts, not semantic AI quality.",
            "Non-RAG scenarios use deterministic service contracts in both modes.",
            (
                "Required answer facts need rubric or human review and are not auto-claimed "
                "as passing."
            ),
        ],
        "cases": cases,
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
