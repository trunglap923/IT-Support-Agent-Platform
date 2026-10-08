"""Measure the current history builder against frozen memory/context scenarios."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agent.context.builder import ContextMessage, build_agent_context
from evals.memory_context.contracts import ContextBaselineCase

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES = ROOT / "evals" / "memory_context" / "cases-v1.jsonl"
DEFAULT_OUTPUT = ROOT / "reports" / "phase0" / "memory-context-baseline.json"
DEFAULT_MARKDOWN = ROOT / "reports" / "phase0" / "memory-context-baseline.md"


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool
    numerator: int
    denominator: int
    details: tuple[str, ...] = ()


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    revision = completed.stdout.strip() or "unknown"
    dirty = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return f"{revision}-dirty" if dirty.stdout.strip() else revision


def _load_cases(path: Path) -> tuple[list[ContextBaselineCase], str]:
    raw = path.read_bytes()
    cases = [
        ContextBaselineCase.model_validate_json(line)
        for line in raw.decode("utf-8").splitlines()
        if line.strip()
    ]
    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Context baseline case IDs must be unique")
    return cases, hashlib.sha256(raw).hexdigest()


def _contains(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def _ratio_check(name: str, outcomes: list[tuple[str, bool]]) -> CheckResult:
    return CheckResult(
        name=name,
        passed=all(passed for _, passed in outcomes),
        numerator=sum(passed for _, passed in outcomes),
        denominator=len(outcomes),
        details=tuple(label for label, passed in outcomes if not passed),
    )


def _evaluate_case(case: ContextBaselineCase) -> dict[str, Any]:
    expected = case.expectations
    options = case.builder_options
    try:
        context = build_agent_context(
            current_query=case.current_query,
            history=[
                ContextMessage(role=message.role, content=message.content)
                for message in case.history
            ],
            max_input_tokens=options.max_input_tokens,
            summary_trigger_messages=options.summary_trigger_messages,
            summary_trigger_tokens=options.summary_trigger_tokens,
            recent_messages_after_summary=options.recent_messages_after_summary,
        )
    except ValueError as error:
        matched = expected.expected_error is not None and expected.expected_error in str(error)
        error_checks = [
            CheckResult(
                name="expected_error",
                passed=matched,
                numerator=int(matched),
                denominator=1,
                details=() if matched else (str(error),),
            )
        ]
        return {
            "case_id": case.case_id,
            "category": case.category,
            "description": case.description,
            "status": "expected_error" if matched else "unexpected_error",
            "checks": [asdict(check) for check in error_checks],
            "passed": all(check.passed for check in error_checks),
            "error": str(error),
        }

    selected_context = "\n".join(
        [
            context.conversation_summary or "",
            *(message.content for message in context.history),
            *(f"Confirmed attempted: {step}" for step in context.confirmed_attempted_steps),
        ]
    )
    confirmed = "\n".join(context.confirmed_attempted_steps)
    checks: list[CheckResult] = []
    no_error_expected = expected.expected_error is None
    checks.append(
        CheckResult(
            name="unexpected_error",
            passed=no_error_expected,
            numerator=int(no_error_expected),
            denominator=1,
            details=() if no_error_expected else ("Builder returned successfully",),
        )
    )
    query_preserved = context.current_query == case.current_query.strip()
    checks.append(
        CheckResult(
            name="current_request_preserved",
            passed=query_preserved,
            numerator=int(query_preserved),
            denominator=1,
        )
    )
    budget_ok = context.estimated_tokens <= options.max_input_tokens
    checks.append(
        CheckResult(
            name="token_budget_compliance",
            passed=budget_ok,
            numerator=int(budget_ok),
            denominator=1,
            details=()
            if budget_ok
            else (f"{context.estimated_tokens}>{options.max_input_tokens}",),
        )
    )
    required = [
        (term, _contains(selected_context, term)) for term in expected.required_context_terms
    ]
    if required:
        checks.append(_ratio_check("critical_context_retention", required))
    forbidden = [
        (term, not _contains(selected_context, term)) for term in expected.forbidden_context_terms
    ]
    if forbidden:
        checks.append(_ratio_check("forbidden_context_exclusion", forbidden))
    required_attempts = [
        (term, _contains(confirmed, term)) for term in expected.required_confirmed_attempt_terms
    ]
    if required_attempts:
        checks.append(_ratio_check("confirmed_attempt_retention", required_attempts))
    forbidden_attempts = [
        (term, not _contains(confirmed, term))
        for term in expected.forbidden_confirmed_attempt_terms
    ]
    if forbidden_attempts:
        checks.append(_ratio_check("suggestion_not_confirmed", forbidden_attempts))
    if expected.must_truncate is not None:
        matched = context.truncated is expected.must_truncate
        checks.append(
            CheckResult(
                name="truncation_state",
                passed=matched,
                numerator=int(matched),
                denominator=1,
                details=()
                if matched
                else (f"expected={expected.must_truncate},actual={context.truncated}",),
            )
        )
    if expected.must_summarize is not None:
        actual = context.conversation_summary is not None
        matched = actual is expected.must_summarize
        checks.append(
            CheckResult(
                name="summarization_state",
                passed=matched,
                numerator=int(matched),
                denominator=1,
                details=() if matched else (f"expected={expected.must_summarize},actual={actual}",),
            )
        )
    return {
        "case_id": case.case_id,
        "category": case.category,
        "description": case.description,
        "status": "completed",
        "checks": [asdict(check) for check in checks],
        "passed": all(check.passed for check in checks),
        "context": {
            "estimated_tokens": context.estimated_tokens,
            "selected_history_messages": len(context.history),
            "truncated": context.truncated,
            "summarized_messages": context.summarized_messages,
            "confirmed_attempted_steps": list(context.confirmed_attempted_steps),
        },
    }


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    checks: dict[str, dict[str, int | float]] = {}
    for case in cases:
        for check in case["checks"]:
            total = checks.setdefault(check["name"], {"numerator": 0, "denominator": 0})
            total["numerator"] += check["numerator"]
            total["denominator"] += check["denominator"]
    for value in checks.values():
        denominator = value["denominator"]
        value["rate"] = round(value["numerator"] / denominator, 6) if denominator else 0.0
    passed = sum(bool(case["passed"]) for case in cases)
    return {
        "case_pass": {
            "numerator": passed,
            "denominator": len(cases),
            "rate": round(passed / len(cases), 6) if cases else 0.0,
        },
        "checks": checks,
    }


def build_report(cases_path: Path) -> dict[str, Any]:
    cases, digest = _load_cases(cases_path)
    results = [_evaluate_case(case) for case in cases]
    return {
        "report_version": "memory-context-baseline-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_revision": _git_revision(),
        "dataset": {
            "path": str(cases_path.relative_to(ROOT)),
            "sha256": digest,
            "case_count": len(cases),
        },
        "system": {
            "component": "app.agent.context.builder.build_agent_context",
            "implementation": "phase-0-observed-baseline",
            "paid_model_calls": 0,
        },
        "metrics": _aggregate(results),
        "known_limitations": [
            (
                "This baseline evaluates the existing history builder, not the proposed "
                "ContextManager."
            ),
            "It does not execute an LLM, tools, RAG, database authorization, or side effects.",
            (
                "A failing gold expectation records an architectural gap and does not make the "
                "runner fail."
            ),
        ],
        "cases": results,
    }


def _write_markdown(report: dict[str, Any], output: Path) -> None:
    metrics = report["metrics"]
    rows = [
        "# Phase 0 memory/context baseline",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        f"Dataset: `{report['dataset']['path']}` (`{report['dataset']['sha256']}`)",
        "",
        f"Cases: **{report['dataset']['case_count']}** · paid model calls: **0**",
        "",
        "## Aggregate metrics",
        "",
        "| Metric | Result |",
        "|---|---:|",
        (
            "| case_pass | "
            f"{metrics['case_pass']['numerator']}/{metrics['case_pass']['denominator']} "
            f"({metrics['case_pass']['rate']:.1%}) |"
        ),
    ]
    for name, value in sorted(metrics["checks"].items()):
        rows.append(
            f"| {name} | {value['numerator']}/{value['denominator']} ({value['rate']:.1%}) |"
        )
    rows.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | Category | Pass | Failed checks |",
            "|---|---|---:|---|",
        ]
    )
    for case in report["cases"]:
        failed = ", ".join(check["name"] for check in case["checks"] if not check["passed"])
        rows.append(
            f"| {case['case_id']} | {case['category']} | "
            f"{'yes' if case['passed'] else 'no'} | {failed or '—'} |"
        )
    rows.extend(
        [
            "",
            "## Interpretation",
            "",
            (
                "Failures are frozen evidence for Phase 1/2 design work. They must not be removed "
                "from the dataset to improve the score; improvements must change the "
                "implementation or add a new versioned benchmark."
            ),
            "",
            "## Limitations",
            "",
            *(f"- {item}" for item in report["known_limitations"]),
            "",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()
    report = build_report(args.cases.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_markdown(report, args.markdown)
    case_pass = report["metrics"]["case_pass"]
    print(
        f"Memory/context baseline: {case_pass['numerator']}/{case_pass['denominator']} "
        f"cases passed; report={args.output}"
    )


if __name__ == "__main__":
    main()
