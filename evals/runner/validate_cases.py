"""Validate the offline evaluation dataset without invoking a model."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

EVALS_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = EVALS_ROOT / "cases" / "development.jsonl"
DEFAULT_SCHEMA = EVALS_ROOT / "cases" / "schema.json"
EXPECTED_M0_COUNTS = {
    "citations": 8,
    "no_answer": 7,
    "permission": 7,
    "tool_safety": 8,
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"{path}:{line_number} must contain a JSON object")
            cases.append(value)
    return cases


def validate_semantics(cases: list[dict[str, Any]]) -> None:
    case_ids = [str(case["case_id"]) for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case_id values must be unique")

    counts = Counter(str(case["category"]) for case in cases)
    if counts != Counter(EXPECTED_M0_COUNTS):
        raise ValueError(
            f"expected category counts {EXPECTED_M0_COUNTS}, got {dict(counts)}"
        )

    for case in cases:
        case_id = str(case["case_id"])
        category = case["category"]
        evidence = case["relevant_evidence"]
        changes = case["expected_db_changes"]
        forbidden = case["forbidden_actions"]
        outcome = case["expected_outcome"]

        if category == "citations":
            if (
                not evidence
                or not case["required_answer_facts"]
                or outcome != "answered"
            ):
                raise ValueError(
                    f"{case_id}: citation case needs evidence, facts and answered outcome"
                )
        elif category == "no_answer":
            if (
                evidence
                or outcome not in {"abstain", "clarify"}
                or "invent_policy" not in forbidden
            ):
                raise ValueError(f"{case_id}: invalid no-answer ground truth")
        elif category == "permission":
            if (
                outcome != "access_denied"
                or "disclose_cross_scope_data" not in forbidden
            ):
                raise ValueError(
                    f"{case_id}: permission case must deny cross-scope disclosure"
                )
        elif category == "tool_safety" and not any(
            action in forbidden
            for action in (
                "write_without_approval",
                "call_unlisted_tool",
                "trust_unverified_context",
            )
        ):
            raise ValueError(
                f"{case_id}: tool-safety case lacks a core safety prohibition"
            )

        if outcome != "ticket_created" and changes:
            raise ValueError(f"{case_id}: unexpected DB changes for {outcome}")
        if outcome == "ticket_created" and (
            len(changes) != 1 or changes[0]["approval_required"] is not True
        ):
            raise ValueError(f"{case_id}: ticket creation needs one approved DB effect")


def validate(cases_path: Path, schema_path: Path) -> Counter[str]:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    cases = load_cases(cases_path)
    for line_number, case in enumerate(cases, start=1):
        errors = sorted(validator.iter_errors(case), key=lambda error: list(error.path))
        if errors:
            details = "; ".join(error.message for error in errors)
            raise ValueError(f"{cases_path}:{line_number}: {details}")
    validate_semantics(cases)
    return Counter(str(case["category"]) for case in cases)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    counts = validate(args.cases, args.schema)
    print(f"Validated {sum(counts.values())} cases: {dict(sorted(counts.items()))}")


if __name__ == "__main__":
    main()
