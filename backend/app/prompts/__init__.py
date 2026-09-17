"""Versioned, checksum-verified prompt assets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

_ROOT = Path(__file__).resolve().parent
_MANIFEST_PATH = _ROOT / "prompt_manifest.json"


@dataclass(frozen=True, slots=True)
class PromptAsset:
    name: str
    version: str
    path: Path
    sha256: str

    def read_text(self) -> str:
        content = self.path.read_text(encoding="utf-8")
        actual = hashlib.sha256(content.encode()).hexdigest()
        if actual != self.sha256:
            raise RuntimeError(f"Prompt checksum mismatch: {self.name}")
        return content.strip()


def _load_manifest() -> dict[str, Any]:
    payload = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Prompt manifest must be an object")
    if payload.get("manifest_version") != "prompt-manifest-v1":
        raise RuntimeError("Unsupported prompt manifest version")
    return cast(dict[str, Any], payload)


def _asset(name: str) -> PromptAsset:
    payload = _load_manifest()
    raw = payload.get("assets", {}).get(name)
    if not isinstance(raw, dict):
        raise RuntimeError(f"Prompt asset is not registered: {name}")
    path = (_ROOT / str(raw["path"])).resolve()
    if not path.is_relative_to(_ROOT) or not path.is_file():
        raise RuntimeError(f"Prompt asset path is invalid: {name}")
    return PromptAsset(
        name=name,
        version=str(raw["version"]),
        path=path,
        sha256=str(raw["sha256"]),
    )


SUPPORT_PROMPT = _asset("support_agent")
MEMORY_EXTRACTION_PROMPT = _asset("memory_extraction")
REPLY_SCHEMA = _asset("support_reply_schema")
SUPPORT_PROMPT_VERSION = SUPPORT_PROMPT.version
MEMORY_PROMPT_VERSION = MEMORY_EXTRACTION_PROMPT.version
REPLY_SCHEMA_VERSION = REPLY_SCHEMA.version
SUPPORT_INSTRUCTIONS = SUPPORT_PROMPT.read_text()


def prompt_versions() -> dict[str, str]:
    return {
        "support_agent": SUPPORT_PROMPT_VERSION,
        "memory_extraction": MEMORY_PROMPT_VERSION,
        "support_reply_schema": REPLY_SCHEMA_VERSION,
    }


__all__ = [
    "MEMORY_EXTRACTION_PROMPT",
    "MEMORY_PROMPT_VERSION",
    "REPLY_SCHEMA",
    "REPLY_SCHEMA_VERSION",
    "SUPPORT_INSTRUCTIONS",
    "SUPPORT_PROMPT",
    "SUPPORT_PROMPT_VERSION",
    "PromptAsset",
    "prompt_versions",
]
