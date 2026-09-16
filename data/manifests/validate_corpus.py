"""Validate the committed knowledge corpus without importing the application."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "data" / "manifests" / "documents.json"
SCHEMA_PATH = ROOT / "data" / "manifests" / "documents.schema.json"
KNOWLEDGE_ROOT = (ROOT / "data" / "knowledge").resolve()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_corpus() -> int:
    manifest = _load(MANIFEST_PATH)
    schema = _load(SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(manifest),
        key=lambda error: list(error.absolute_path),
    )
    messages = [f"schema: {error.json_path}: {error.message}" for error in errors]
    identities: set[tuple[str, str]] = set()
    listed_paths: set[Path] = set()

    for item in manifest.get("documents", []):
        identity = (item.get("document_key", ""), item.get("version_label", ""))
        if identity in identities:
            messages.append(f"duplicate identity: {identity[0]}:{identity[1]}")
        identities.add(identity)

        relative_path = Path(item.get("path", ""))
        candidate = (KNOWLEDGE_ROOT / relative_path).resolve()
        if not candidate.is_relative_to(KNOWLEDGE_ROOT):
            messages.append(f"path escapes knowledge root: {relative_path}")
            continue
        listed_paths.add(candidate)
        if not candidate.is_file():
            messages.append(f"missing corpus file: {relative_path}")
            continue
        digest = "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
        if digest != item.get("checksum"):
            messages.append(f"checksum mismatch: {relative_path}")

        visibility = item.get("visibility")
        department_key = item.get("department_key")
        if (visibility == "department") != (department_key is not None):
            messages.append(f"invalid department scope: {identity[0]}:{identity[1]}")

        effective = datetime.fromisoformat(item["effective_at"].replace("Z", "+00:00"))
        expires_raw = item.get("expires_at")
        if expires_raw is not None:
            expires = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
            if expires <= effective:
                messages.append(f"expiry is not after effective date: {identity[0]}:{identity[1]}")

    corpus_paths = {path.resolve() for path in KNOWLEDGE_ROOT.glob("*.md")}
    corpus_paths.discard((KNOWLEDGE_ROOT / "README.md").resolve())
    corpus_paths.discard((KNOWLEDGE_ROOT / "PLAN.md").resolve())
    for path in sorted(corpus_paths - listed_paths):
        messages.append(f"unlisted corpus file: {path.relative_to(KNOWLEDGE_ROOT)}")

    if messages:
        raise SystemExit("Corpus validation failed:\n- " + "\n- ".join(messages))
    print(f"Validated {len(identities)} corpus versions in {manifest['snapshot']['id']}.")
    return len(identities)


if __name__ == "__main__":
    validate_corpus()
