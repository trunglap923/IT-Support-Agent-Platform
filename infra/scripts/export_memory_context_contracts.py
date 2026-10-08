"""Export deterministic JSON schemas for memory/context architecture contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.memory_context.contracts import ContextBaselineCase

from app.agent.context.contracts import (
    ActiveContext,
    ContextBuildRequest,
    ContextCandidate,
)
from app.agent.working_memory.contracts import (
    NormalizedToolObservation,
    WorkingMemorySnapshot,
)
from app.memory.contracts import MemoryDecisionRecord, MemoryMutationProposal

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / "docs" / "contracts"

CONTRACTS = {
    "context-candidate-v1.schema.json": ContextCandidate,
    "context-build-request-v1.schema.json": ContextBuildRequest,
    "active-context-v1.schema.json": ActiveContext,
    "working-memory-v1.schema.json": WorkingMemorySnapshot,
    "tool-observation-v1.schema.json": NormalizedToolObservation,
    "memory-mutation-proposal-v1.schema.json": MemoryMutationProposal,
    "memory-decision-v1.schema.json": MemoryDecisionRecord,
    "context-baseline-case-v1.schema.json": ContextBaselineCase,
}


def _schema(model: Any, filename: str) -> dict[str, Any]:
    schema = model.model_json_schema(mode="validation")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"urn:it-support-agent:schema:{filename.removesuffix('.schema.json')}"
    return schema


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for filename, model in CONTRACTS.items():
        destination = OUTPUT_ROOT / filename
        destination.write_text(
            json.dumps(_schema(model, filename), indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        print(destination.relative_to(ROOT))


if __name__ == "__main__":
    main()
