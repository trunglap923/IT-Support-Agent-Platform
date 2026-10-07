"""Deterministic, runtime-neutral selection of one bounded model context."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from app.agent.context.builder import estimate_tokens
from app.agent.context.contracts import (
    ActiveContext,
    ActiveContextMessage,
    ContextBuildRequest,
    ContextCandidate,
    ContextConflict,
    ContextSelection,
)

CONTEXT_POLICY_VERSION = "context-manager-v1"

_LANE_BY_KIND = {
    "system_policy": "system",
    "tool_schema": "system",
    "current_request": "request",
    "working_memory": "request",
    "conversation_history": "history",
    "tool_observation": "observation",
    "knowledge": "knowledge",
    "semantic_memory": "memory",
    "episodic_memory": "memory",
    "procedural_memory": "procedure",
}
_BASE_LANE_WEIGHTS = {
    "system": 0.15,
    "request": 0.25,
    "history": 0.12,
    "observation": 0.18,
    "knowledge": 0.18,
    "memory": 0.07,
    "procedure": 0.05,
}
_INJECTION = re.compile(
    r"(?:ignore|disregard)\s+(?:all\s+)?(?:previous|system)\s+instructions|"
    r"system\s+prompt|developer\s+message|bỏ\s+qua\s+(?:mọi\s+)?(?:chỉ dẫn|hướng dẫn)",
    re.IGNORECASE,
)


def _priority(candidate: ContextCandidate) -> int:
    if candidate.required:
        return 0
    if candidate.kind in {"working_memory", "tool_observation", "knowledge"}:
        return 1
    if candidate.kind in {"semantic_memory", "episodic_memory", "procedural_memory"}:
        return 2
    return 3


def _utility(candidate: ContextCandidate, lane_budget: int) -> float:
    token_penalty = min(0.25, candidate.token_cost / max(1, lane_budget))
    score = (
        0.30 * candidate.relevance
        + 0.20 * candidate.task_utility
        + 0.15 * candidate.source_reliability
        + 0.10 * candidate.confidence
        + 0.10 * candidate.temporal_validity
        + 0.08 * candidate.recency
        + 0.07 * candidate.importance
        - token_penalty
    )
    return max(-1.0, min(1.0, score))


def _render(candidate: ContextCandidate, content: str | None = None) -> ActiveContextMessage:
    value = (content if content is not None else candidate.content).strip()
    if candidate.kind == "current_request":
        return ActiveContextMessage(
            role="user", content=value, candidate_ids=(candidate.candidate_id,)
        )
    role = candidate.message_role or "user"
    if candidate.kind != "conversation_history":
        value = (
            f'<context_item kind="{candidate.kind}" source_ref="{candidate.source_ref}" '
            'trust="data">\n'
            f"{value}\n</context_item>"
        )
        # Context data must never gain the authority of a system or tool message.
        role = "user"
    return ActiveContextMessage(role=role, content=value, candidate_ids=(candidate.candidate_id,))


def _compress(candidate: ContextCandidate, token_limit: int) -> tuple[str, str]:
    char_limit = max(80, token_limit * 2)
    content = candidate.content.strip()
    if len(content) > char_limit:
        content = content[: max(1, char_limit - 1)].rstrip() + "…"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return content, f"context-summary:{digest}"


@dataclass(frozen=True, slots=True)
class DeterministicContextManager:
    """Apply scope, conflict, utility and token-budget rules without model calls."""

    minimum_utility: float = 0.20

    def build(self, request: ContextBuildRequest) -> ActiveContext:
        input_limit = request.token_budget.input_token_limit
        lane_budgets = {
            lane: max(1, int(input_limit * weight)) for lane, weight in _BASE_LANE_WEIGHTS.items()
        }
        if request.purpose in {"plan", "tool_selection"}:
            lane_budgets["knowledge"] //= 2
            lane_budgets["request"] += lane_budgets["knowledge"]
        elif request.purpose == "answer":
            lane_budgets["knowledge"] += lane_budgets["procedure"]
            lane_budgets["procedure"] = 0

        by_id = {candidate.candidate_id: candidate for candidate in request.candidates}
        decisions: dict[str, ContextSelection] = {}
        eligible: list[ContextCandidate] = []
        content_hashes: set[str] = set()
        for candidate in request.candidates:
            reason: str | None = None
            if candidate.scope.agent_namespace != "it_support":
                reason = "namespace_mismatch"
            elif candidate.scope.owner_id not in {None, self._owner_id(request)}:
                reason = "owner_scope_mismatch"
            elif candidate.scope.department_id not in {None, self._department_id(request)}:
                reason = "department_scope_mismatch"
            elif candidate.sensitivity == "restricted":
                reason = "restricted_content"
            elif candidate.kind != "current_request" and _INJECTION.search(candidate.content):
                reason = "prompt_injection_quarantined"
            digest = hashlib.sha256(candidate.content.strip().encode("utf-8")).hexdigest()
            if reason is None and digest in content_hashes and not candidate.required:
                reason = "duplicate_content"
            if (
                reason is None
                and candidate.kind in {"conversation_history", "semantic_memory", "episodic_memory"}
                and candidate.relevance < 0.15
                and candidate.task_utility < 0.15
            ):
                reason = "unrelated_to_current_request"
            if (
                reason is None
                and candidate.source_ref.startswith("device:")
                and candidate.relevance < 0.15
            ):
                reason = "device_context_not_needed"
            if reason is not None and not candidate.required:
                decisions[candidate.candidate_id] = ContextSelection(
                    candidate_id=candidate.candidate_id,
                    action="drop",
                    reason_code=reason,
                )
                continue
            content_hashes.add(digest)
            eligible.append(candidate)

        conflicts, blocked = self._resolve_conflicts(eligible, by_id)
        used = 0
        lane_used: dict[str, int] = defaultdict(int)
        messages: list[ActiveContextMessage] = []
        deferred: list[tuple[ContextCandidate, float]] = []
        current = by_id[request.current_request_candidate_id]
        current_cost = estimate_tokens(current.content)
        if current_cost > input_limit:
            raise ValueError("Current request exceeds the active-context input budget")
        lane_used["request"] = current_cost

        ranked = sorted(
            (item for item in eligible if item.candidate_id != current.candidate_id),
            key=lambda item: (
                _priority(item),
                -_utility(item, lane_budgets[_LANE_BY_KIND[item.kind]]),
                -item.recency,
                item.candidate_id,
            ),
        )
        for candidate in ranked:
            lane = _LANE_BY_KIND[candidate.kind]
            score = _utility(candidate, lane_budgets[lane])
            if candidate.candidate_id in blocked:
                decisions[candidate.candidate_id] = ContextSelection(
                    candidate_id=candidate.candidate_id,
                    action="drop",
                    reason_code="unresolved_conflict",
                    utility_score=score,
                )
                continue
            if score < self.minimum_utility and not candidate.required:
                decisions[candidate.candidate_id] = ContextSelection(
                    candidate_id=candidate.candidate_id,
                    action="drop",
                    reason_code="low_utility",
                    utility_score=score,
                )
                continue
            remaining = input_limit - current_cost - used
            lane_remaining = lane_budgets[lane] - lane_used[lane]
            allowed = remaining if candidate.required else min(remaining, max(0, lane_remaining))
            rendered = _render(candidate)
            cost = estimate_tokens(rendered.content)
            if cost <= allowed:
                messages.append(rendered)
                used += cost
                lane_used[lane] += cost
                decisions[candidate.candidate_id] = ContextSelection(
                    candidate_id=candidate.candidate_id,
                    action="keep",
                    reason_code="required" if candidate.required else "selected_by_utility",
                    utility_score=score,
                    allocated_tokens=cost,
                )
            elif not candidate.required and cost <= remaining and cost > lane_remaining:
                deferred.append((candidate, score))
            elif allowed >= 48 and candidate.kind != "conversation_history":
                compacted, artifact_ref = _compress(candidate, max(1, allowed - 32))
                rendered = _render(candidate, compacted)
                cost = estimate_tokens(rendered.content)
                if cost <= allowed:
                    messages.append(rendered)
                    used += cost
                    lane_used[lane] += cost
                    decisions[candidate.candidate_id] = ContextSelection(
                        candidate_id=candidate.candidate_id,
                        action="compress",
                        reason_code="compressed_to_budget",
                        utility_score=score,
                        allocated_tokens=cost,
                        derived_artifact_ref=artifact_ref,
                    )
                    continue
                if candidate.required:
                    raise ValueError("Required context cannot fit the active-context budget")
                decisions[candidate.candidate_id] = ContextSelection(
                    candidate_id=candidate.candidate_id,
                    action="drop",
                    reason_code="insufficient_budget",
                    utility_score=score,
                )
            else:
                if candidate.required:
                    raise ValueError("Required context cannot fit the active-context budget")
                decisions[candidate.candidate_id] = ContextSelection(
                    candidate_id=candidate.candidate_id,
                    action="drop",
                    reason_code="lane_budget_exhausted",
                    utility_score=score,
                )

        # A lane may borrow capacity that other lanes did not use, while the global
        # model limit remains a hard boundary.
        for candidate, score in deferred:
            remaining = input_limit - current_cost - used
            rendered = _render(candidate)
            cost = estimate_tokens(rendered.content)
            if cost <= remaining:
                messages.append(rendered)
                used += cost
                lane_used[_LANE_BY_KIND[candidate.kind]] += cost
                decisions[candidate.candidate_id] = ContextSelection(
                    candidate_id=candidate.candidate_id,
                    action="keep",
                    reason_code="borrowed_unused_lane_budget",
                    utility_score=score,
                    allocated_tokens=cost,
                )
            else:
                decisions[candidate.candidate_id] = ContextSelection(
                    candidate_id=candidate.candidate_id,
                    action="drop",
                    reason_code="global_budget_exhausted",
                    utility_score=score,
                )

        messages.append(_render(current))
        decisions[current.candidate_id] = ContextSelection(
            candidate_id=current.candidate_id,
            action="keep",
            reason_code="current_request_required",
            utility_score=1.0,
            allocated_tokens=current_cost,
        )
        for candidate in request.candidates:
            decisions.setdefault(
                candidate.candidate_id,
                ContextSelection(
                    candidate_id=candidate.candidate_id,
                    action="drop",
                    reason_code="not_selected",
                ),
            )
        selections = tuple(decisions[item.candidate_id] for item in request.candidates)
        estimated = sum(estimate_tokens(message.content) for message in messages)
        canonical = json.dumps(
            {
                "run_id": str(request.run_id),
                "call_sequence": request.call_sequence,
                "purpose": request.purpose,
                "messages": [message.model_dump(mode="json") for message in messages],
                "selections": [selection.model_dump(mode="json") for selection in selections],
                "conflicts": [conflict.model_dump(mode="json") for conflict in conflicts],
                "policy_version": request.policy_version,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return ActiveContext(
            run_id=request.run_id,
            call_sequence=request.call_sequence,
            purpose=request.purpose,
            current_request=request.current_request,
            messages=tuple(messages),
            selections=selections,
            conflicts=conflicts,
            token_budget=request.token_budget,
            estimated_input_tokens=estimated,
            bundle_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            policy_version=request.policy_version,
        )

    @staticmethod
    def _owner_id(request: ContextBuildRequest) -> UUID | None:
        current = next(
            item
            for item in request.candidates
            if item.candidate_id == request.current_request_candidate_id
        )
        return current.scope.owner_id

    @staticmethod
    def _department_id(request: ContextBuildRequest) -> UUID | None:
        current = next(
            item
            for item in request.candidates
            if item.candidate_id == request.current_request_candidate_id
        )
        return current.scope.department_id

    @staticmethod
    def _resolve_conflicts(
        eligible: list[ContextCandidate],
        by_id: dict[str, ContextCandidate],
    ) -> tuple[tuple[ContextConflict, ...], set[str]]:
        conflicts: list[ContextConflict] = []
        blocked: set[str] = set()
        seen: set[frozenset[str]] = set()
        eligible_ids = {item.candidate_id for item in eligible}
        for candidate in eligible:
            group = frozenset(
                {candidate.candidate_id, *candidate.conflicts_with}.intersection(eligible_ids)
            )
            if len(group) < 2 or group in seen:
                continue
            seen.add(group)
            items = [by_id[item_id] for item_id in group]
            ranked = sorted(
                items,
                key=lambda item: (item.source_reliability, item.temporal_validity, item.recency),
                reverse=True,
            )
            winner = ranked[0]
            runner_up = ranked[1]
            decisive = (
                winner.source_reliability - runner_up.source_reliability >= 0.15
                or winner.recency - runner_up.recency >= 0.20
            )
            if decisive:
                blocked.update(group - {winner.candidate_id})
                conflicts.append(
                    ContextConflict(
                        subject="context_claim",
                        predicate="value",
                        candidate_ids=tuple(sorted(group)),
                        resolution=(
                            "authoritative_source"
                            if winner.source_reliability > runner_up.source_reliability
                            else "newest_valid"
                        ),
                        selected_candidate_id=winner.candidate_id,
                    )
                )
            else:
                blocked.update(group)
                conflicts.append(
                    ContextConflict(
                        subject="context_claim",
                        predicate="value",
                        candidate_ids=tuple(sorted(group)),
                        resolution="clarification_required",
                    )
                )
        return tuple(conflicts), blocked
