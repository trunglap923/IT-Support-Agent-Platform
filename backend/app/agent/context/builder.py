"""Build a bounded context while always preserving the current user query."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

from app.agent.context.summary import summarize_conversation

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
    conversation_summary: str | None
    summarized_messages: int
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
    confirmed.extend(match.group(1).strip() for match in _CONFIRMED_STEP.finditer(current_query))
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
    summary_trigger_messages: int = 20,
    summary_trigger_tokens: int = 6_000,
    recent_messages_after_summary: int = 12,
) -> AgentContext:
    query = current_query.strip()
    if not query:
        raise ValueError("Current query cannot be empty")
    query_tokens = estimate_tokens(query)
    if query_tokens > max_input_tokens:
        raise ValueError("Current query exceeds the model input budget")

    nonempty_history = [message for message in history if message.content.strip()]
    dialogue = [message for message in nonempty_history if message.role != "memory"]
    memories = [message for message in nonempty_history if message.role == "memory"]
    dialogue_tokens = sum(estimate_tokens(message.content) for message in dialogue)
    should_summarize = (
        len(dialogue) > summary_trigger_messages or dialogue_tokens > summary_trigger_tokens
    )
    older_dialogue: list[ContextMessage] = []
    recent_dialogue = dialogue
    if should_summarize:
        split_at = max(0, len(dialogue) - recent_messages_after_summary)
        older_dialogue = dialogue[:split_at]
        recent_dialogue = dialogue[split_at:]
    conversation_summary = summarize_conversation(
        [(message.role, message.content) for message in older_dialogue]
    )
    candidate_history = [*recent_dialogue, *memories]

    suggested_steps, confirmed_attempted_steps = _support_steps(query, nonempty_history)
    summary_lines = [
        *(f"Suggested: {step}" for step in suggested_steps),
        *(f"Confirmed attempted: {step}" for step in confirmed_attempted_steps),
    ]
    support_summary_tokens = estimate_tokens("\n".join(summary_lines)) if summary_lines else 0
    conversation_summary_tokens = (
        estimate_tokens(conversation_summary) if conversation_summary else 0
    )
    if query_tokens + support_summary_tokens + conversation_summary_tokens > max_input_tokens:
        suggested_steps = ()
        summary_lines = [
            *(f"Confirmed attempted: {step}" for step in confirmed_attempted_steps),
        ]
        support_summary_tokens = estimate_tokens("\n".join(summary_lines)) if summary_lines else 0
    if query_tokens + support_summary_tokens + conversation_summary_tokens > max_input_tokens:
        conversation_summary = None
        conversation_summary_tokens = 0
    if query_tokens + support_summary_tokens > max_input_tokens:
        confirmed_attempted_steps = ()
        support_summary_tokens = 0

    remaining = (
        max_input_tokens - query_tokens - support_summary_tokens - conversation_summary_tokens
    )
    selected_reversed: list[ContextMessage] = []
    used = query_tokens + support_summary_tokens + conversation_summary_tokens
    for message in reversed(candidate_history):
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
        truncated=bool(older_dialogue) or len(selected) < len(candidate_history),
        conversation_summary=conversation_summary,
        summarized_messages=len(older_dialogue) if conversation_summary else 0,
        suggested_steps=suggested_steps,
        confirmed_attempted_steps=confirmed_attempted_steps,
    )
