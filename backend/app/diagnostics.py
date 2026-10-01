"""Safe, grep-friendly JSON diagnostics for API and agent execution."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any


def content_log_fields(
    name: str,
    value: str,
    *,
    include_content: bool,
    max_chars: int = 4_000,
) -> dict[str, Any]:
    """Describe text without exposing it unless explicitly enabled."""

    encoded = value.encode("utf-8")
    fields: dict[str, Any] = {
        f"{name}_chars": len(value),
        f"{name}_bytes": len(encoded),
        f"{name}_sha256": hashlib.sha256(encoded).hexdigest()[:16],
    }
    if include_content:
        fields[name] = value[:max_chars]
        fields[f"{name}_truncated"] = len(value) > max_chars
    return fields


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    exc_info: bool = False,
    **fields: Any,
) -> None:
    """Write one structured event while preserving traceback support."""

    target = logger
    if logger.disabled or not logger.hasHandlers():
        target = logging.getLogger("uvicorn.error")
    target.disabled = False
    if target.level == logging.NOTSET:
        target.setLevel(logging.INFO)
    payload = {"event": event, "component": logger.name, **fields}
    target.log(
        level,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
        exc_info=exc_info,
    )
