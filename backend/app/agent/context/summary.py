"""Deterministic, bounded compaction for older conversation turns."""

from __future__ import annotations

from collections.abc import Sequence


def summarize_conversation(
    messages: Sequence[tuple[str, str]],
    *,
    max_items: int = 8,
    max_item_chars: int = 180,
) -> str | None:
    """Return a labelled extractive summary without turning assistant text into user fact."""

    dialogue = [
        (role, content)
        for role, content in messages
        if role in {"user", "assistant"} and content.strip()
    ]
    if not dialogue:
        return None

    lines = ["Earlier conversation summary (extractive, untrusted):"]
    for role, content in dialogue[-max_items:]:
        normalized = " ".join(content.strip().split())
        if len(normalized) > max_item_chars:
            normalized = normalized[: max_item_chars - 1].rstrip() + "…"
        label = "User said" if role == "user" else "Assistant previously suggested"
        lines.append(f"- {label}: {normalized}")
    return "\n".join(lines)
