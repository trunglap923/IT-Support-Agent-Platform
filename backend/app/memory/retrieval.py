"""Retrieve confirmed memory as bounded, server-labelled agent context."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context.builder import ContextMessage, estimate_tokens
from app.agent.context.contracts import ContextCandidate, ContextScope
from app.db.models import MemoryAssertion, MemoryFact
from app.memory.hybrid import (
    HybridMemoryItem,
    HybridMemoryQuery,
    HybridMemoryRetriever,
    recency_score,
)

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
        hybrid_query: HybridMemoryQuery | None = None,
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
                .limit(max(100, limit * 10))
            )
        )
        prepared = hybrid_query or HybridMemoryQuery.lexical(query)
        ranked = HybridMemoryRetriever().rank(
            prepared,
            [
                HybridMemoryItem(
                    item_id=str(value.id),
                    text=value.normalized_text,
                    embedding=(tuple(value.embedding) if value.embedding is not None else None),
                    embedding_model=value.embedding_model,
                    embedding_dimensions=value.embedding_dimensions,
                    exact_terms=(value.predicate, *_PREDICATE_ALIASES.get(value.predicate, ())),
                    recency=recency_score(value.updated_at, now=current_time),
                    confidence=float(value.confidence),
                    authority=value.authority_tier / 100,
                )
                for value in values
            ],
            limit=limit,
        )
        values_by_id = {str(value.id): value for value in values}
        candidates: list[ContextCandidate] = []
        for score in ranked:
            value = values_by_id[score.item_id]
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
                    relevance=score.relevance,
                    importance=0.7,
                    source_reliability=value.authority_tier / 100,
                    confidence=float(value.confidence),
                    temporal_validity=1,
                    task_utility=score.score,
                    recency=score.recency,
                    token_cost=estimate_tokens(content),
                    sensitivity="confidential",
                    provenance_refs=(f"memory-source:{value.source_id}",),
                )
            )
        return tuple(candidates)

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
