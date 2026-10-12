"""Adapters that normalize runtime state into scoped context candidates."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.agent.context.builder import estimate_tokens
from app.agent.context.contracts import ContextCandidate, ContextScope
from app.agent.context.schemas import SupportContext
from app.agent.working_memory.contracts import WorkingMemorySnapshot

_TOKEN = re.compile(r"[\w]+(?:[.-][\w]+)*", re.UNICODE)


def _id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:{digest}"


def _terms(value: str) -> set[str]:
    return {item.casefold() for item in _TOKEN.findall(value) if len(item) > 1}


def _relevance(query: str, content: str) -> float:
    query_terms = _terms(query)
    if not query_terms:
        return 0.0
    overlap = query_terms.intersection(_terms(content))
    return min(1.0, len(overlap) / max(1, min(6, len(query_terms))))


def scope_for_support(support: SupportContext) -> ContextScope:
    return ContextScope(
        owner_id=support.principal.user_id,
        department_id=support.principal.department_id,
    )


def support_candidates(
    support: SupportContext,
    query: str,
    *,
    transform_previous: bool = False,
) -> tuple[ContextCandidate, ...]:
    scope = scope_for_support(support)
    candidates: list[ContextCandidate] = [
        ContextCandidate(
            candidate_id="request:current",
            kind="current_request",
            content=query.strip(),
            source_ref="current_user_message",
            scope=scope,
            relevance=1,
            importance=1,
            source_reliability=1,
            confidence=1,
            temporal_validity=1,
            task_utility=1,
            recency=1,
            token_cost=estimate_tokens(query),
            sensitivity="confidential",
            required=True,
            message_role="user",
        )
    ]
    history = list(support.history)
    if transform_previous:
        # Formatting requests operate on the last assistant answer. Do not let older
        # topics or memory entries compete with the content being transformed.
        latest_assistant = next(
            (
                (index, message)
                for index, message in reversed(list(enumerate(history)))
                if message.role == "assistant" and message.content.strip()
            ),
            None,
        )
        if latest_assistant is not None:
            index, message = latest_assistant
            content = message.content.strip()
            candidates.append(
                ContextCandidate(
                    candidate_id=_id("history", f"{index}:{message.role}:{content}"),
                    kind="conversation_history",
                    content=content,
                    source_ref=f"conversation:{support.conversation_id}:message:{index}",
                    scope=scope,
                    relevance=1,
                    importance=1,
                    source_reliability=1,
                    confidence=1,
                    temporal_validity=1,
                    task_utility=1,
                    recency=1,
                    token_cost=estimate_tokens(content),
                    sensitivity="confidential",
                    required=True,
                    message_role="assistant",
                )
            )
        return tuple(candidates)

    total = max(1, len(history))
    recent_history_start = max(0, total - 4)
    for index, message in enumerate(history):
        content = message.content.strip()
        if not content:
            continue
        relevance = _relevance(query, content)
        recent_turn = index >= recent_history_start
        if not recent_turn and relevance < 0.5:
            relevance = 0.0
        candidates.append(
            ContextCandidate(
                candidate_id=_id("history", f"{index}:{message.role}:{content}"),
                kind="conversation_history",
                content=content,
                source_ref=f"conversation:{support.conversation_id}:message:{index}",
                scope=scope,
                relevance=relevance,
                importance=0.45,
                source_reliability=0.75 if message.role == "user" else 0.55,
                confidence=0.75,
                temporal_validity=1,
                # Recency may rank relevant history higher, but must not make an
                # unrelated recent topic eligible on its own.
                task_utility=relevance,
                recency=(index + 1) / total,
                token_cost=estimate_tokens(content),
                sensitivity="confidential",
                message_role=message.role if message.role != "memory" else "user",
            )
        )
    for index, message in enumerate(support.memories):
        content = message.content.strip()
        if not content:
            continue
        relevance = _relevance(query, content)
        candidates.append(
            ContextCandidate(
                candidate_id=_id("memory", f"{index}:{content}"),
                kind="semantic_memory",
                content=content,
                source_ref=f"confirmed_memory:{index}",
                scope=scope,
                relevance=relevance,
                importance=0.65,
                source_reliability=0.9,
                confidence=1,
                temporal_validity=1,
                task_utility=relevance,
                recency=0.8,
                token_cost=estimate_tokens(content),
                sensitivity="confidential",
            )
        )
    if support.device is not None:
        content = (
            f"Active conversation device: {support.device.label}; "
            f"platform={support.device.platform}; device_id={support.device.id}"
        )
        candidates.append(
            ContextCandidate(
                candidate_id=f"device:{support.device.id}",
                kind="working_memory",
                content=content,
                source_ref=f"device:{support.device.id}",
                scope=scope,
                relevance=_relevance(query, content),
                importance=0.75,
                source_reliability=1,
                confidence=1,
                temporal_validity=1,
                task_utility=_relevance(query, content),
                token_cost=estimate_tokens(content),
                sensitivity="confidential",
            )
        )
    return tuple(candidates)


def working_memory_candidates(
    snapshot: WorkingMemorySnapshot | None,
    *,
    scope: ContextScope,
    query: str,
) -> tuple[ContextCandidate, ...]:
    if snapshot is None:
        return ()
    values: list[tuple[str, str, bool, float, float]] = []
    if " ".join(snapshot.goal.statement.casefold().split()) != " ".join(query.casefold().split()):
        values.append(("goal", snapshot.goal.statement, True, 1.0, 1.0))
    active_steps = [
        f"{step.step_id}: {step.title} [{step.status}]"
        for step in snapshot.plan.steps
        if step.status in {"pending", "running", "failed", "blocked"}
    ]
    if active_steps:
        procedure = (
            f"\nPinned approved procedure version: {snapshot.plan.procedure_version_id}"
            if snapshot.plan.procedure_version_id is not None
            else ""
        )
        values.append(
            (
                "plan",
                "Active plan:\n" + "\n".join(active_steps) + procedure,
                False,
                0.9,
                0.9,
            )
        )
    for action in snapshot.pending_actions:
        values.append(
            (
                f"pending:{action.action_id}",
                f"Pending action {action.tool_name}; approval_required={action.requires_approval}",
                True,
                1.0,
                1.0,
            )
        )
    pending_verification = [
        item.statement for item in snapshot.verification_requirements if item.status == "pending"
    ]
    if pending_verification:
        values.append(
            (
                "verification",
                "Verification required:\n" + "\n".join(pending_verification),
                True,
                1,
                1,
            )
        )
    candidates: list[ContextCandidate] = []
    for key, content, required, importance, utility in values:
        candidates.append(
            ContextCandidate(
                candidate_id=f"working:{key}",
                kind="working_memory",
                content=content,
                source_ref=f"working_memory:{snapshot.working_memory_id}:v{snapshot.version}",
                scope=scope,
                relevance=max(_relevance(query, content), 0.75 if required else 0.4),
                importance=importance,
                source_reliability=1,
                confidence=1,
                temporal_validity=1,
                task_utility=utility,
                token_cost=estimate_tokens(content),
                sensitivity="confidential",
                required=required,
            )
        )
    observations = list(snapshot.observations[-12:])
    total = max(1, len(observations))
    for index, observation in enumerate(observations):
        content = observation.summary.strip()
        if observation.source_type == "user" and " ".join(content.casefold().split()) == " ".join(
            query.casefold().split()
        ):
            continue
        candidates.append(
            ContextCandidate(
                candidate_id=f"observation:{observation.observation_id}",
                kind="tool_observation" if observation.source_type == "tool" else "working_memory",
                content=content,
                source_ref=observation.source_ref,
                scope=scope,
                relevance=max(_relevance(query, content), 0.45),
                importance=0.8,
                source_reliability=observation.reliability,
                confidence=observation.reliability,
                temporal_validity=1,
                task_utility=0.8,
                recency=(index + 1) / total,
                token_cost=estimate_tokens(content),
                sensitivity="confidential",
                provenance_refs=(observation.raw_artifact_ref,)
                if observation.raw_artifact_ref
                else (),
            )
        )
    return tuple(candidates)


def evidence_candidates(
    evidence: Sequence[Mapping[str, Any]],
    *,
    scope: ContextScope,
    query: str,
) -> tuple[ContextCandidate, ...]:
    candidates: list[ContextCandidate] = []
    for item in evidence:
        source_id = str(item["source_id"])
        title = str(item.get("title", "Internal knowledge"))
        excerpt = str(item.get("excerpt", "")).strip()
        content = f"[{source_id}] {title}\n{excerpt}"
        score = max(0.0, min(1.0, float(item.get("score", 0))))
        candidates.append(
            ContextCandidate(
                candidate_id=f"knowledge:{source_id}",
                kind="knowledge",
                content=content,
                source_ref=source_id,
                scope=scope,
                relevance=max(score, _relevance(query, content)),
                importance=0.9,
                source_reliability=0.95,
                confidence=score,
                temporal_validity=1,
                task_utility=score,
                token_cost=estimate_tokens(content),
                sensitivity="internal",
                provenance_refs=tuple(
                    str(item[key])
                    for key in ("document_id", "version_id", "chunk_id")
                    if item.get(key)
                ),
            )
        )
    return tuple(candidates)
