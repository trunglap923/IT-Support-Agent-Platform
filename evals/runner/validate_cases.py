"""Validate the offline evaluation dataset without invoking a model."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

EVALS_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = EVALS_ROOT.parent
DOCUMENT_MANIFEST = PROJECT_ROOT / "data" / "manifests" / "documents.json"
KNOWLEDGE_ROOT = PROJECT_ROOT / "data" / "knowledge"
DEFAULT_CASES = (
    EVALS_ROOT / "cases" / "development.jsonl",
    EVALS_ROOT / "cases" / "holdout.jsonl",
)
DEFAULT_SCHEMA = EVALS_ROOT / "cases" / "schema.json"
EXPECTED_CATEGORY_COUNTS = dict.fromkeys(
    ("rag", "permission", "tool", "approval", "memory", "failure"), 20
)
EXPECTED_SPLIT_COUNTS = {"development": 80, "holdout": 40}


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


def _normalize_span(value: str) -> str:
    return " ".join(value.split()).casefold()


def validate_evidence_references(cases: list[dict[str, Any]]) -> None:
    manifest = load_json(DOCUMENT_MANIFEST)
    snapshot = manifest["snapshot"]
    documents = {
        (str(item["document_key"]), str(item["version_label"])): item
        for item in manifest["documents"]
    }
    loaded_sources: dict[str, str] = {}
    for case in cases:
        case_id = str(case["case_id"])
        if case["document_snapshot"] != snapshot["id"]:
            raise ValueError(
                f"{case_id}: document_snapshot does not match manifest snapshot {snapshot['id']}"
            )
        for evidence in case["relevant_evidence"]:
            key = (str(evidence["document_key"]), str(evidence["version_label"]))
            document = documents.get(key)
            if document is None:
                raise ValueError(f"{case_id}: evidence document/version does not exist: {key}")
            relative_path = str(document["path"])
            content = loaded_sources.setdefault(
                relative_path,
                (KNOWLEDGE_ROOT / relative_path).read_text(encoding="utf-8"),
            )
            heading = f"## {evidence['section']}"
            if heading.casefold() not in content.casefold():
                raise ValueError(f"{case_id}: evidence section is absent from {relative_path}")
            if _normalize_span(str(evidence["span"])) not in _normalize_span(content):
                raise ValueError(f"{case_id}: evidence span is absent from {relative_path}")


def validate_semantics(cases: list[dict[str, Any]]) -> None:
    case_ids = [str(case["case_id"]) for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("case_id values must be unique")

    counts = Counter(str(case["category"]) for case in cases)
    if counts != Counter(EXPECTED_CATEGORY_COUNTS):
        raise ValueError(f"expected category counts {EXPECTED_CATEGORY_COUNTS}, got {dict(counts)}")
    split_counts = Counter(str(case["split"]) for case in cases)
    if split_counts != Counter(EXPECTED_SPLIT_COUNTS):
        raise ValueError(f"expected split counts {EXPECTED_SPLIT_COUNTS}, got {dict(split_counts)}")
    group_splits: dict[str, set[str]] = {}
    for case in cases:
        group_splits.setdefault(str(case["scenario_group"]), set()).add(str(case["split"]))
    leaked_groups = sorted(group for group, splits in group_splits.items() if len(splits) != 1)
    if leaked_groups:
        raise ValueError(f"scenario groups cross splits: {leaked_groups}")

    validate_evidence_references(cases)

    for case in cases:
        case_id = str(case["case_id"])
        category = case["category"]
        evidence = case["relevant_evidence"]
        changes = case["expected_db_changes"]
        forbidden = case["forbidden_actions"]
        outcome = case["expected_outcome"]

        if category == "rag":
            if outcome == "answered" and (not evidence or not case["required_answer_facts"]):
                raise ValueError(f"{case_id}: answered RAG case needs evidence and facts")
            if outcome in {"abstain", "clarify"} and (evidence or "invent_policy" not in forbidden):
                raise ValueError(f"{case_id}: invalid RAG no-answer ground truth")
        elif category == "permission":
            if outcome != "access_denied" or "disclose_cross_scope_data" not in forbidden:
                raise ValueError(f"{case_id}: permission case must deny cross-scope disclosure")
        elif category == "tool" and not any(
            action in forbidden
            for action in (
                "call_unlisted_tool",
                "disclose_cross_scope_data",
                "trust_unverified_context",
            )
        ):
            raise ValueError(f"{case_id}: tool case lacks a core safety prohibition")
        elif category == "approval" and "write_without_approval" not in forbidden:
            raise ValueError(f"{case_id}: approval case must prohibit unapproved writes")
        elif category == "memory" and not any(
            action in forbidden
            for action in (
                "write_memory_without_consent",
                "reuse_deleted_memory",
                "cross_device_memory",
            )
        ):
            raise ValueError(f"{case_id}: memory case lacks lifecycle protection")
        elif category == "failure" and not case["injected_failures"]:
            raise ValueError(f"{case_id}: failure case needs injected_failures")

        if outcome == "ticket_created" and (
            len(changes) != 1 or changes[0]["approval_required"] is not True
        ):
            raise ValueError(f"{case_id}: ticket creation needs one approved DB effect")
        for change in changes:
            if change["resource"] == "ticket" and category != "approval":
                raise ValueError(f"{case_id}: ticket effect belongs to approval category")
            if change["resource"] == "memory" and category != "memory":
                raise ValueError(f"{case_id}: memory effect belongs to memory category")
            if change["resource"] == "run" and category != "failure":
                raise ValueError(f"{case_id}: run effect belongs to failure category")


def validate(cases_paths: list[Path], schema_path: Path) -> Counter[str]:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    cases: list[dict[str, Any]] = []
    for cases_path in cases_paths:
        loaded = load_cases(cases_path)
        for line_number, case in enumerate(loaded, start=1):
            errors = sorted(validator.iter_errors(case), key=lambda error: list(error.path))
            if errors:
                details = "; ".join(error.message for error in errors)
                raise ValueError(f"{cases_path}:{line_number}: {details}")
        cases.extend(loaded)
    validate_semantics(cases)
    return Counter(str(case["category"]) for case in cases)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", action="append", type=Path)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    counts = validate(args.cases or list(DEFAULT_CASES), args.schema)
    print(f"Validated {sum(counts.values())} cases: {dict(sorted(counts.items()))}")


if __name__ == "__main__":
    main()
