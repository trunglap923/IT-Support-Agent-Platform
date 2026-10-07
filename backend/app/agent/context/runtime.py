"""Per-run context builder with durable, content-minimized audit records."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context.adapters import (
    evidence_candidates,
    scope_for_support,
    support_candidates,
    working_memory_candidates,
)
from app.agent.context.contracts import (
    ActiveContext,
    ContextBuildRequest,
    ContextCandidate,
    ContextPurpose,
    ContextTokenBudget,
)
from app.agent.context.manager import CONTEXT_POLICY_VERSION, DeterministicContextManager
from app.agent.context.schemas import SupportContext
from app.agent.working_memory.service import WorkingMemoryService
from app.db import Database
from app.db.models import ContextBuildRecord, ContextSummaryArtifact
from app.diagnostics import log_event

logger = logging.getLogger(__name__)


class RuntimeContextBuilder:
    """Refresh working state and build one ActiveContext for each owned model call."""

    def __init__(
        self,
        *,
        database: Database,
        run_id: UUID,
        support: SupportContext,
        model_context_limit: int = 16_000,
        reserved_output_tokens: int = 1_200,
        audit_retention_days: int = 7,
        policy_version: str = CONTEXT_POLICY_VERSION,
    ) -> None:
        self._database = database
        self._run_id = run_id
        self._support = support
        self._base = support_candidates(support, support.query)
        self._scope = scope_for_support(support)
        self._manager = DeterministicContextManager()
        self._policy_version = policy_version
        self._audit_retention_days = audit_retention_days
        safety_margin = max(1, int(model_context_limit * 0.10))
        available = model_context_limit - reserved_output_tokens - safety_margin
        self._budget = ContextTokenBudget(
            model_context_limit=model_context_limit,
            reserved_output_tokens=reserved_output_tokens,
            safety_margin_tokens=safety_margin,
            # Constant system instructions and provider-owned tool schemas remain
            # outside ActiveContext, so keep their 15% lane reserved here.
            input_token_limit=max(1, int(available * 0.85)),
        )

    @property
    def input_token_limit(self) -> int:
        return self._budget.input_token_limit

    async def build(
        self,
        purpose: ContextPurpose,
        *,
        evidence: Sequence[Mapping[str, Any]] = (),
    ) -> ActiveContext:
        async with self._database.session() as session, session.begin():
            now = datetime.now(UTC)
            await session.execute(
                delete(ContextSummaryArtifact).where(ContextSummaryArtifact.expires_at <= now)
            )
            await session.execute(
                delete(ContextBuildRecord).where(ContextBuildRecord.expires_at <= now)
            )
            snapshot = await WorkingMemoryService().load(
                session,
                run_id=self._run_id,
                owner_id=self._support.principal.user_id,
            )
            extra = evidence_candidates(
                evidence,
                scope=self._scope,
                query=self._support.query,
            )
            candidates: tuple[ContextCandidate, ...] = (
                *self._base,
                *working_memory_candidates(snapshot, scope=self._scope, query=self._support.query),
                *extra,
            )
            latest = await session.scalar(
                select(func.max(ContextBuildRecord.call_sequence)).where(
                    ContextBuildRecord.run_id == self._run_id
                )
            )
            call_sequence = int(latest or 0) + 1
            active = self._manager.build(
                ContextBuildRequest(
                    run_id=self._run_id,
                    call_sequence=call_sequence,
                    purpose=purpose,
                    current_request=self._support.query,
                    current_request_candidate_id="request:current",
                    candidates=candidates,
                    token_budget=self._budget,
                    policy_version=self._policy_version,
                )
            )
            self._persist(session, active)
            log_event(
                logger,
                "agent.context.built",
                run_id=str(active.run_id),
                call_sequence=active.call_sequence,
                purpose=active.purpose,
                bundle_hash=active.bundle_hash,
                estimated_input_tokens=active.estimated_input_tokens,
                input_token_limit=active.token_budget.input_token_limit,
                selected_count=sum(item.action != "drop" for item in active.selections),
                excluded_count=sum(item.action == "drop" for item in active.selections),
                compressed_count=sum(item.action == "compress" for item in active.selections),
                conflict_count=len(active.conflicts),
                policy_version=active.policy_version,
            )
            return active

    def _persist(self, session: AsyncSession, active: ActiveContext) -> None:
        expires_at = datetime.now(UTC) + timedelta(days=self._audit_retention_days)
        selections = [
            {
                "candidate_id": item.candidate_id,
                "action": item.action,
                "reason_code": item.reason_code,
                "utility_score": item.utility_score,
                "allocated_tokens": item.allocated_tokens,
                "derived_artifact_ref": item.derived_artifact_ref,
            }
            for item in active.selections
        ]
        session.add(
            ContextBuildRecord(
                run_id=active.run_id,
                owner_id=self._support.principal.user_id,
                call_sequence=active.call_sequence,
                purpose=active.purpose,
                policy_version=active.policy_version,
                bundle_hash=active.bundle_hash,
                estimated_input_tokens=active.estimated_input_tokens,
                input_token_limit=active.token_budget.input_token_limit,
                selected_count=sum(item.action != "drop" for item in active.selections),
                excluded_count=sum(item.action == "drop" for item in active.selections),
                conflict_count=len(active.conflicts),
                selections=selections,
                conflicts=[item.model_dump(mode="json") for item in active.conflicts],
                expires_at=expires_at,
            )
        )
        messages_by_candidate = {
            candidate_id: message.content
            for message in active.messages
            for candidate_id in message.candidate_ids
        }
        for selection in active.selections:
            if selection.action != "compress" or selection.derived_artifact_ref is None:
                continue
            content = messages_by_candidate.get(selection.candidate_id, "")
            session.add(
                ContextSummaryArtifact(
                    id=uuid4(),
                    run_id=active.run_id,
                    owner_id=self._support.principal.user_id,
                    call_sequence=active.call_sequence,
                    artifact_ref=selection.derived_artifact_ref,
                    source_candidate_ids=[selection.candidate_id],
                    content=content,
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    token_count=selection.allocated_tokens,
                    policy_version=active.policy_version,
                    expires_at=expires_at,
                )
            )


def active_context_history(active: ActiveContext) -> list[tuple[str, str]]:
    """Render a bundle for provider APIs that receive history separately from query."""

    return [(item.role, item.content) for item in active.messages[:-1]]
