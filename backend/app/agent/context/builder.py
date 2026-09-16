"""Build a bounded context while always preserving the current user query."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ContextMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class AgentContext:
    current_query: str
    history: tuple[ContextMessage, ...]
    estimated_tokens: int
    truncated: bool


def estimate_tokens(value: str) -> int:
    return max(1, math.ceil(len(value.encode("utf-8")) / 3))


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

    remaining = max_input_tokens - query_tokens
    selected_reversed: list[ContextMessage] = []
    used = query_tokens
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
    )
