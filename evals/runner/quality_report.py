"""Generate reviewed G-01..G-09, performance and cost artifacts."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from evals.runner.load_cases import load_cases
from evals.runner.metrics import calculate_report_cost, measure_local_fake_load
from evals.runner.report import git_revision

ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent-report",
        type=Path,
        default=ROOT / "reports/raw/agent-evaluation-fake.json",
    )
    parser.add_argument(
        "--test-evidence",
        type=Path,
        default=ROOT / "reports/runs/wp13-local-gates.json",
    )
    parser.add_argument(
        "--retrieval-report",
        type=Path,
        default=ROOT / "reports/retrieval-baseline.json",
    )
    parser.add_argument(
        "--json-output", type=Path, default=ROOT / "reports/product-quality.json"
    )
    parser.add_argument(
        "--summary-output", type=Path, default=ROOT / "reports/evaluation-summary.md"
    )
    parser.add_argument(
        "--performance-output", type=Path, default=ROOT / "reports/performance-cost.md"
    )
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _suite_gate(
    gate_id: str,
    name: str,
    threshold: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    suite = evidence.get("suites", {}).get(gate_id)
    if suite is None:
        return {
            "id": gate_id,
            "name": name,
            "threshold": threshold,
            "status": "not_measured",
            "measurement": "No PostgreSQL regression artifact was supplied.",
        }
    counts = suite["counts"]
    return {
        "id": gate_id,
        "name": name,
        "threshold": threshold,
        "status": suite["status"],
        "measurement": {
            "passed_tests": counts["passed"],
            "denominator": sum(counts.values()),
            "failed": counts["failed"] + counts["error"] + counts["skipped"],
        },
        "evidence": "reports/runs/wp13-local-gates.json",
        "limitation": "Zero incidents applies only to the named automated regression suite.",
    }


def _write_markdown(report: dict[str, Any], summary: Path, performance: Path) -> None:
    rows = ["| Gate | Status | Measurement |", "|---|---|---|"]
    for gate in report["gates"]:
        measurement = gate["measurement"]
        if isinstance(measurement, dict):
            measurement_text = ", ".join(
                f"{key}={value}" for key, value in measurement.items()
            )
        else:
            measurement_text = measurement
        rows.append(
            f"| {gate['id']} · {gate['name']} | {gate['status']} | {measurement_text} |"
        )
    summary.write_text(
        "# Product quality report — G-01 to G-09\n\n"
        f"Generated from commit `{report['git_revision']}`. Release decision: "
        f"**{report['release_decision']}**.\n\n"
        + "\n".join(rows)
        + "\n\n## Interpretation\n\n"
        "`not_measured` is intentional: fake-provider contract checks do not establish live "
        "model quality or full-stack latency. Thresholds were not changed after seeing results.\n",
        encoding="utf-8",
    )
    load = report["measurements"]["local_fake_load"]
    cost = report["measurements"]["agent_cost"]
    performance.write_text(
        "# Performance and cost measurement\n\n"
        "## Local load probe\n\n"
        f"- Workload: {load['workload']}\n"
        f"- Requests: {load['request_count']} in {load['batches']} batches at concurrency "
        f"{load['concurrency']}\n"
        f"- P50/P95/max active latency: {load['p50_ms']} / {load['p95_ms']} / "
        f"{load['max_ms']} ms\n"
        f"- Failures: {load['failures']}\n"
        "- This is an in-process deterministic probe, so it does **not** qualify for G-09.\n\n"
        "## Cost\n\n"
        f"- Mode/model: {cost['mode']} / `{cost['model']}`\n"
        f"- Tokens: {cost['input_tokens']} input, {cost['output_tokens']} output\n"
        f"- Calculated cost: USD {cost['calculated_cost_usd']} "
        f"({cost['billing_status']})\n"
        "- A fake run demonstrates accounting shape only; it is not a live cost claim.\n",
        encoding="utf-8",
    )


async def main_async() -> None:
    args = parse_args()
    agent = _load(args.agent_report)
    retrieval = _load(args.retrieval_report)
    test_evidence = _load(args.test_evidence) if args.test_evidence.exists() else {}
    load = await measure_local_fake_load()
    cost = calculate_report_cost(
        agent, input_price=Decimal("0.40"), output_price=Decimal("1.60")
    )
    cases = {case.case_id: case for case in load_cases(agent["split"])}
    rag_runs = [
        item for item in agent["cases"] if cases[item["case_id"]].category == "rag"
    ]
    citation_valid = sum(item["scores"]["citations_valid"] for item in rag_runs)
    no_answer_runs = [
        item
        for item in rag_runs
        if cases[item["case_id"]].expected_outcome in {"abstain", "clarify"}
    ]
    no_answer_pass = sum(item["scores"]["outcome_match"] for item in no_answer_runs)
    retrieval_gate = retrieval["metrics"]["g04_recall_gate"]
    memory_safety = test_evidence.get("suites", {}).get("G-08-safety")
    gates = [
        _suite_gate("G-01", "authorization", "0 data leaks", test_evidence),
        _suite_gate("G-02", "side effects", "0 unapproved writes", test_evidence),
        _suite_gate("G-03", "duplicate/recovery", "exactly one ticket", test_evidence),
        {
            "id": "G-04",
            "name": "retrieval",
            "threshold": "Recall@5 >= 0.85",
            "status": "pass" if retrieval_gate["passed"] else "fail",
            "measurement": retrieval["metrics"]["recall_at_5"],
            "evidence": "reports/retrieval-baseline.json",
            "limitation": "Development corpus with deterministic fake embeddings.",
        },
        {
            "id": "G-05",
            "name": "citations",
            "threshold": "100% valid IDs and >=90% supported claims",
            "status": "not_measured",
            "measurement": {
                "valid_source_ids": citation_valid,
                "source_id_denominator": len(rag_runs),
                "human_reviewed_claims": 0,
            },
            "limitation": "ID integrity passed in fake mode; semantic claim review has not run.",
        },
        {
            "id": "G-06",
            "name": "answerability",
            "threshold": ">=90% safe no-answer decisions",
            "status": "not_measured",
            "measurement": {
                "fake_contract_pass": no_answer_pass,
                "fake_contract_denominator": len(no_answer_runs),
            },
            "limitation": "Deterministic expected output cannot establish live-model behavior.",
        },
        {
            "id": "G-07",
            "name": "task success",
            "threshold": ">=85% end-to-end",
            "status": "not_measured",
            "measurement": "Non-RAG eval cases currently use scripted service contracts.",
        },
        {
            "id": "G-08",
            "name": "memory",
            "threshold": ">=90% tasks; 0 cross-user/deleted reuse",
            "status": "not_measured",
            "measurement": {
                "safety_suite": memory_safety["status"] if memory_safety else "not_run",
                "scripted_agent_accuracy_denominator": 0,
            },
            "limitation": "Persistence safety is tested; agent-level memory accuracy is not measured.",
        },
        {
            "id": "G-09",
            "name": "performance",
            "threshold": "P95 end-to-end <=20s at concurrency 3",
            "status": "not_measured",
            "measurement": {
                "local_fake_p95_ms": load["p95_ms"],
                "concurrency": load["concurrency"],
            },
            "limitation": "The measured in-process probe is not a full-stack end-to-end workload.",
        },
    ]
    report = {
        "schema_version": "product-quality-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_revision": git_revision(ROOT),
        "dataset_sha256": agent["dataset_sha256"],
        "agent_report": {
            "mode": agent["mode"],
            "model": agent["model"],
            "run_count": agent["run_count"],
            "result_digest": agent["result_digest"],
        },
        "release_decision": "not_ready"
        if any(gate["status"] != "pass" for gate in gates)
        else "ready",
        "gates": gates,
        "measurements": {"local_fake_load": load, "agent_cost": cost},
    }
    args.json_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _write_markdown(report, args.summary_output, args.performance_output)
    print(
        f"Quality report generated: {sum(gate['status'] == 'pass' for gate in gates)}/9 "
        f"gates pass; decision={report['release_decision']}"
    )


if __name__ == "__main__":
    asyncio.run(main_async())
