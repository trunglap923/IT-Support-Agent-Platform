"""Deterministic ADD/UPDATE/DELETE/NOOP policy for semantic memory."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MemoryAssertion, MemoryConflict, MemoryDecision
from app.memory.contracts import MemoryDecisionRecord, MemoryMutationProposal
from app.memory.sources import MemorySourceRegistry

MEMORY_POLICY_VERSION = "memory-policy-v1"
_FORBIDDEN_PREDICATES = {
    "authorization",
    "permission",
    "role",
    "password",
    "secret",
    "token",
    "system_instruction",
}


@dataclass(frozen=True, slots=True)
class DecisionApplication:
    record: MemoryDecisionRecord
    assertion: MemoryAssertion | None = None
    conflict: MemoryConflict | None = None


def _canonical(value: dict[str, object]) -> tuple[str, str]:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return rendered, hashlib.sha256(rendered.encode("utf-8")).hexdigest()


class MemoryDecisionEngine:
    """Validate proposals and apply one auditable owner-scoped mutation."""

    async def apply(
        self,
        session: AsyncSession,
        *,
        proposal: MemoryMutationProposal,
        decided_by_type: str,
        decided_by_id: UUID | None,
        correlation_id: str,
        run_id: UUID | None = None,
        scope: str = "global",
        device_id: UUID | None = None,
        compatibility_fact_id: UUID | None = None,
        safe_excerpt: str | None = None,
        message_id: UUID | None = None,
        now: datetime | None = None,
    ) -> DecisionApplication:
        current_time = now or datetime.now(UTC)
        prior = await session.scalar(
            select(MemoryDecision).where(MemoryDecision.proposal_id == proposal.proposal_id)
        )
        if prior is not None:
            assertion = (
                await session.get(MemoryAssertion, prior.resulting_assertion_id)
                if prior.resulting_assertion_id is not None
                else None
            )
            return DecisionApplication(self._record(prior), assertion)

        sources = [
            await MemorySourceRegistry().capture(
                session,
                owner_id=proposal.owner_id,
                reference=item,
                safe_excerpt=safe_excerpt,
                message_id=message_id,
                run_id=run_id,
            )
            for item in proposal.evidence
        ]
        target = None
        if proposal.target_memory_id is not None:
            target = await session.scalar(
                select(MemoryAssertion)
                .where(
                    MemoryAssertion.id == proposal.target_memory_id,
                    MemoryAssertion.owner_id == proposal.owner_id,
                )
                .with_for_update()
            )
        active = await session.scalar(
            select(MemoryAssertion)
            .where(
                MemoryAssertion.owner_id == proposal.owner_id,
                MemoryAssertion.subject_type == proposal.subject_type,
                MemoryAssertion.subject_id == proposal.subject_id,
                MemoryAssertion.predicate == proposal.predicate,
                MemoryAssertion.status == "active",
                MemoryAssertion.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if target is None and proposal.operation in {"update", "delete"}:
            return await self._finish(
                session,
                proposal=proposal,
                decided_by_type=decided_by_type,
                decided_by_id=decided_by_id,
                correlation_id=correlation_id,
                run_id=run_id,
                status="rejected",
                operation=proposal.operation,
                reason="target_not_found",
                source_ids=[item.id for item in sources],
                target=None,
                result=None,
            )
        if proposal.predicate.casefold() in _FORBIDDEN_PREDICATES:
            return await self._finish(
                session,
                proposal=proposal,
                decided_by_type=decided_by_type,
                decided_by_id=decided_by_id,
                correlation_id=correlation_id,
                run_id=run_id,
                status="rejected",
                operation=proposal.operation,
                reason="forbidden_predicate",
                source_ids=[item.id for item in sources],
                target=target,
                result=None,
            )
        if proposal.operation == "delete" and target is not None:
            target.status = "deleted"
            target.valid_to = current_time
            target.deleted_at = current_time
            target.version += 1
            return await self._finish(
                session,
                proposal=proposal,
                decided_by_type=decided_by_type,
                decided_by_id=decided_by_id,
                correlation_id=correlation_id,
                run_id=run_id,
                status="accepted",
                operation="delete",
                reason="owner_requested_delete",
                source_ids=[item.id for item in sources],
                target=target,
                result=None,
            )
        if proposal.operation == "noop":
            return await self._finish(
                session,
                proposal=proposal,
                decided_by_type=decided_by_type,
                decided_by_id=decided_by_id,
                correlation_id=correlation_id,
                run_id=run_id,
                status="accepted",
                operation="noop",
                reason=proposal.reason_code,
                source_ids=[item.id for item in sources],
                target=target,
                result=None,
            )

        assert proposal.proposed_value is not None
        rendered, value_hash = _canonical(proposal.proposed_value)
        if active is not None and active.value_hash == value_hash:
            return await self._finish(
                session,
                proposal=proposal,
                decided_by_type=decided_by_type,
                decided_by_id=decided_by_id,
                correlation_id=correlation_id,
                run_id=run_id,
                status="accepted",
                operation="noop",
                reason="duplicate_active_assertion",
                source_ids=[item.id for item in sources],
                target=active,
                result=None,
            )

        authority = max(item.authority_tier for item in sources)
        status = "active"
        if active is not None and authority < active.authority_tier:
            status = "quarantined"
        assertion = MemoryAssertion(
            owner_id=proposal.owner_id,
            source_id=sources[0].id,
            subject_type=proposal.subject_type,
            subject_id=proposal.subject_id,
            predicate=proposal.predicate,
            value=proposal.proposed_value,
            normalized_text=f"{proposal.predicate}: {rendered}"[:1000],
            value_hash=value_hash,
            scope=scope,
            device_id=device_id,
            status=status,
            authority_tier=authority,
            confidence=Decimal(str(proposal.confidence)),
            valid_from=current_time,
            supersedes_id=active.id if active is not None and status == "active" else None,
            compatibility_fact_id=compatibility_fact_id,
        )
        session.add(assertion)
        if active is not None and status == "active":
            active.status = "superseded"
            active.valid_to = current_time
            active.version += 1
        await session.flush()
        conflict = None
        if active is not None:
            conflict = MemoryConflict(
                owner_id=proposal.owner_id,
                subject_type=proposal.subject_type,
                subject_id=proposal.subject_id,
                predicate=proposal.predicate,
                assertion_a_id=active.id,
                assertion_b_id=assertion.id,
                status="quarantined" if status == "quarantined" else "resolved",
                resolution=(
                    "higher_authority_retained"
                    if status == "quarantined"
                    else "newest_authoritative"
                ),
                selected_assertion_id=active.id if status == "quarantined" else assertion.id,
                reviewed_at=current_time,
            )
            session.add(conflict)
        return await self._finish(
            session,
            proposal=proposal,
            decided_by_type=decided_by_type,
            decided_by_id=decided_by_id,
            correlation_id=correlation_id,
            run_id=run_id,
            status="quarantined" if status == "quarantined" else "accepted",
            operation="update" if active is not None else "add",
            reason="lower_authority_conflict" if status == "quarantined" else proposal.reason_code,
            source_ids=[item.id for item in sources],
            target=active,
            result=assertion if status == "active" else None,
            conflict=conflict,
        )

    async def _finish(
        self,
        session: AsyncSession,
        *,
        proposal: MemoryMutationProposal,
        decided_by_type: str,
        decided_by_id: UUID | None,
        correlation_id: str,
        run_id: UUID | None,
        status: str,
        operation: str,
        reason: str,
        source_ids: list[UUID],
        target: MemoryAssertion | None,
        result: MemoryAssertion | None,
        conflict: MemoryConflict | None = None,
    ) -> DecisionApplication:
        row = MemoryDecision(
            id=uuid4(),
            proposal_id=proposal.proposal_id,
            owner_id=proposal.owner_id,
            run_id=run_id,
            operation=operation,
            status=status,
            decided_by_type=decided_by_type,
            decided_by_id=decided_by_id,
            policy_version=MEMORY_POLICY_VERSION,
            reason_code=reason,
            target_assertion_id=target.id if target else None,
            resulting_assertion_id=result.id if result else None,
            source_ids=[str(item) for item in source_ids],
            correlation_id=correlation_id,
            safe_metadata={"proposal_reason": proposal.reason_code},
        )
        session.add(row)
        await session.flush()
        return DecisionApplication(self._record(row), result, conflict)

    @staticmethod
    def _record(row: MemoryDecision) -> MemoryDecisionRecord:
        return MemoryDecisionRecord(
            decision_id=row.id,
            proposal_id=row.proposal_id,
            owner_id=row.owner_id,
            operation=row.operation,
            status=row.status,
            decided_by_type=row.decided_by_type,
            decided_by_id=row.decided_by_id,
            policy_version=row.policy_version,
            reason_code=row.reason_code,
            resulting_memory_id=row.resulting_assertion_id,
            decided_at=row.created_at,
        )
