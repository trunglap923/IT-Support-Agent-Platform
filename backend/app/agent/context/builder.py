"""Build a bounded context while always preserving the current user query."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

_CONFIRMED_STEP = re.compile(
    r"(?:tôi đã|mình đã|đã thử|i tried|i have tried|i already)\s+([^.!?\n]{3,160})",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ContextMessage:
    role: Literal["user", "assistant", "memory"]
    content: str


@dataclass(frozen=True, slots=True)
class AgentContext:
    current_query: str
    history: tuple[ContextMessage, ...]
    estimated_tokens: int
    truncated: bool
    suggested_steps: tuple[str, ...]
    confirmed_attempted_steps: tuple[str, ...]


def estimate_tokens(value: str) -> int:
    return max(1, math.ceil(len(value.encode("utf-8")) / 3))


def _support_steps(
    current_query: str,
    history: list[ContextMessage],
    *,
    limit: int = 8,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    suggested: list[str] = []
    confirmed: list[str] = []
    for message in history:
        content = " ".join(message.content.strip().split())
        if not content:
            continue
        if message.role == "assistant":
            suggested.append(content[:160])
        elif message.role == "user":
            confirmed.extend(match.group(1).strip() for match in _CONFIRMED_STEP.finditer(content))
    confirmed.extend(
        match.group(1).strip() for match in _CONFIRMED_STEP.finditer(current_query)
    )
    # A suggested assistant step never becomes "attempted" unless the user later
    # states it explicitly. Keep only recent, de-duplicated values in each lane.
    return (
        tuple(dict.fromkeys(suggested[-limit:])),
        tuple(dict.fromkeys(confirmed[-limit:])),
    )


def build_agent_context(
    *,
    current_query: str,
    history: list[ContextMessage],
    max_input_tokens: int = 10_000,
) -> AgentContext:
    query = current_query.strip()
    if not query:
        raise ValueError("Current query cannot be empty")
    query_tokens = estimate_tokens(query)
    if query_tokens > max_input_tokens:
        raise ValueError("Current query exceeds the model input budget")

    suggested_steps, confirmed_attempted_steps = _support_steps(query, history)
    summary_lines = [
        *(f"Suggested: {step}" for step in suggested_steps),
        *(f"Confirmed attempted: {step}" for step in confirmed_attempted_steps),
    ]
    summary_tokens = estimate_tokens("\n".join(summary_lines)) if summary_lines else 0
    if query_tokens + summary_tokens > max_input_tokens:
        suggested_steps = ()
        summary_lines = [
            *(f"Confirmed attempted: {step}" for step in confirmed_attempted_steps),
        ]
        summary_tokens = estimate_tokens("\n".join(summary_lines)) if summary_lines else 0
    if query_tokens + summary_tokens > max_input_tokens:
        confirmed_attempted_steps = ()
        summary_tokens = 0

    remaining = max_input_tokens - query_tokens - summary_tokens
    selected_reversed: list[ContextMessage] = []
    used = query_tokens + summary_tokens
    for message in reversed(history):
        content = message.content.strip()
        if not content:
            continue
        cost = estimate_tokens(content)
        if cost > remaining:
            continue
        selected_reversed.append(ContextMessage(role=message.role, content=content))
        remaining -= cost
        used += cost
    selected = tuple(reversed(selected_reversed))
    return AgentContext(
        current_query=query,
        history=selected,
        estimated_tokens=used,
        truncated=len(selected) < len([message for message in history if message.content.strip()]),
        suggested_steps=suggested_steps,
        confirmed_attempted_steps=confirmed_attempted_steps,
    )
