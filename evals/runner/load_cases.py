"""Typed loading and deterministic selection for evaluation cases."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CASES_ROOT = ROOT / "evals" / "cases"


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    split: str
    scenario_group: str
    category: str
    language: str
    actor: dict[str, str]
    initial_state: dict[str, Any]
    document_snapshot: str
    messages: list[dict[str, str]]
    expected_outcome: str
    allowed_tool_sequences: list[list[str]]
    forbidden_actions: list[str]
    relevant_evidence: list[dict[str, str]]
    required_answer_facts: list[str]
    forbidden_answer_facts: list[str]
    expected_db_changes: list[dict[str, Any]]
    injected_failures: list[str]
    rubric_version: str


def load_cases(split: str = "development") -> list[EvaluationCase]:
    splits = ("development", "holdout") if split == "all" else (split,)
    cases: list[EvaluationCase] = []
    for selected in splits:
        path = CASES_ROOT / f"{selected}.jsonl"
        cases.extend(
            EvaluationCase(**json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return cases


def select_cases(
    cases: list[EvaluationCase],
    *,
    category: str | None,
    max_cases: int | None,
    seed: int,
) -> list[EvaluationCase]:
    selected = [case for case in cases if category is None or case.category == category]
    selected.sort(key=lambda case: case.case_id)
    if max_cases is not None and max_cases < len(selected):
        random.Random(seed).shuffle(selected)
        selected = sorted(selected[:max_cases], key=lambda case: case.case_id)
    return selected


def dataset_digest(cases: list[EvaluationCase]) -> str:
    canonical = json.dumps(
        [asdict(case) for case in cases],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
