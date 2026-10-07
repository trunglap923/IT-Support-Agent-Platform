"""Retrieve confirmed memory as bounded, server-labelled agent context."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context.builder import ContextMessage, estimate_tokens
from app.agent.context.contracts import ContextCandidate, ContextScope
from app.db.models import MemoryAssertion, MemoryFact

MAX_MEMORY_CONTEXT_FACTS = 5
_PREDICATE_ALIASES: dict[str, tuple[str, ...]] = {
    "preferred_language": ("ngôn ngữ", "tiếng", "language"),
    "operating_system": ("hệ điều hành", "windows", "ubuntu", "macos", " os "),
    "device_label": ("tên thiết bị", "tên máy", "device", "label"),
}


class MemoryContextService:
    async def context_candidates(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        device_id: UUID | None,
        query: str,
        scope: ContextScope,
        now: datetime | None = None,
        limit: int = 12,
    ) -> tuple[ContextCandidate, ...]:
        current_time = now or datetime.now(UTC)
        scope_filter = MemoryAssertion.scope == "global"
        if device_id is not None:
            scope_filter = or_(
                scope_filter,
                and_(MemoryAssertion.scope == "device", MemoryAssertion.device_id == device_id),
            )
        values = list(
            await session.scalars(
                select(MemoryAssertion)
                .where(
                    MemoryAssertion.owner_id == owner_id,
                    MemoryAssertion.status == "active",
                    MemoryAssertion.deleted_at.is_(None),
                    or_(
                        MemoryAssertion.valid_to.is_(None), MemoryAssertion.valid_to > current_time
                    ),
                    scope_filter,
                )
                .order_by(
                    MemoryAssertion.authority_tier.desc(),
                    MemoryAssertion.updated_at.desc(),
                )
                .limit(limit * 3)
            )
        )
        query_terms = _terms(query)
        candidates: list[ContextCandidate] = []
        normalized_query = f" {' '.join(query.casefold().split())} "
        for value in values:
            relevance = _overlap(query_terms, _terms(value.normalized_text))
            aliases = _PREDICATE_ALIASES.get(value.predicate, ())
            alias_match = any(alias in normalized_query for alias in aliases)
            if alias_match:
                relevance = max(relevance, 0.8)
            if relevance <= 0 and value.predicate.casefold() not in normalized_query:
                continue
            content = (
                f"Confirmed memory ({value.predicate}): {value.value.get('value', value.value)}"
            )
            candidates.append(
                ContextCandidate(
                    candidate_id=f"assertion:{value.id}",
                    kind="semantic_memory",
                    content=content,
                    source_ref=f"memory-assertion:{value.id}:v{value.version}",
                    scope=scope,
                    relevance=max(relevance, 0.35),
                    importance=0.7,
                    source_reliability=value.authority_tier / 100,
                    confidence=float(value.confidence),
                    temporal_validity=1,
                    task_utility=max(relevance, 0.35),
                    recency=0.85,
                    token_cost=estimate_tokens(content),
                    sensitivity="confidential",
                    provenance_refs=(f"memory-source:{value.source_id}",),
                )
            )
        return tuple(candidates[:limit])

    async def context_messages(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        device_id: UUID | None,
        now: datetime | None = None,
    ) -> list[ContextMessage]:
        current_time = now or datetime.now(UTC)
        scope_filter = MemoryFact.scope == "global"
        if device_id is not None:
            scope_filter = or_(
                scope_filter,
                and_(MemoryFact.scope == "device", MemoryFact.device_id == device_id),
            )
        values = list(
            await session.scalars(
                select(MemoryFact)
                .where(
                    MemoryFact.owner_id == owner_id,
                    MemoryFact.deleted_at.is_(None),
                    MemoryFact.expires_at > current_time,
                    scope_filter,
                )
                .order_by(MemoryFact.updated_at.desc(), MemoryFact.id)
                .limit(MAX_MEMORY_CONTEXT_FACTS)
            )
        )
        return [
            ContextMessage(
                role="memory",
                content=f"Confirmed user data: {value.key}={value.value}",
            )
            for value in values
        ]


_TOKEN = re.compile(r"[\w.-]+", re.UNICODE)


def _terms(value: str) -> set[str]:
    return {item.casefold() for item in _TOKEN.findall(value) if len(item) > 1}


def _overlap(left: set[str], right: set[str]) -> float:
    if not left:
        return 0.0
    return min(1.0, len(left.intersection(right)) / max(1, min(6, len(left))))
