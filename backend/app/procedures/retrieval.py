"""Scope and applicability-aware procedural-memory retrieval."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context.builder import estimate_tokens
from app.agent.context.contracts import ContextCandidate, ContextScope
from app.auth.principal import Principal
from app.db.models import (
    Document,
    DocumentVersion,
    DocumentVersionStatus,
    Procedure,
    ProcedureApplicability,
    ProcedureStep,
    ProcedureVersion,
)
from app.tools.registry import TOOL_REGISTRY

_TOKEN = re.compile(r"[\w.-]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class ProcedureMatch:
    version_id: UUID
    candidate: ContextCandidate
    matched_signals: tuple[str, ...]


def _terms(value: str) -> set[str]:
    return {item.casefold() for item in _TOKEN.findall(value) if len(item) > 1}


def _wilson_lower(success: int, failure: int) -> float:
    total = success + failure
    if total == 0:
        return 0.5
    z = 1.96
    proportion = success / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    margin = z * math.sqrt((proportion * (1 - proportion) + z * z / (4 * total)) / total)
    return max(0.0, (centre - margin) / denominator)


class ProcedureRetriever:
    async def retrieve(
        self,
        session: AsyncSession,
        *,
        principal: Principal,
        query: str,
        scope: ContextScope,
        now: datetime | None = None,
        limit: int = 2,
    ) -> tuple[ProcedureMatch, ...]:
        current = now or datetime.now(UTC)
        visibility_scope = or_(
            ProcedureVersion.visibility == "company",
            (
                (ProcedureVersion.visibility == "department")
                & (ProcedureVersion.department_id == principal.department_id)
            ),
        )
        if principal.role.value in {"it", "admin"}:
            visibility_scope = or_(visibility_scope, ProcedureVersion.visibility == "it_only")
        current_source = exists().where(
            DocumentVersion.id == ProcedureVersion.source_document_version_id,
            Document.id == DocumentVersion.document_id,
            Document.current_version_id == DocumentVersion.id,
            Document.archived.is_(False),
            DocumentVersion.status == DocumentVersionStatus.PUBLISHED,
        )
        rows = list(
            (
                await session.execute(
                    select(Procedure, ProcedureVersion)
                    .join(ProcedureVersion, ProcedureVersion.id == Procedure.current_version_id)
                    .where(
                        ProcedureVersion.status == "approved",
                        ProcedureVersion.effective_from <= current,
                        visibility_scope,
                        or_(
                            ProcedureVersion.source_document_version_id.is_(None),
                            current_source,
                        ),
                        or_(
                            ProcedureVersion.effective_to.is_(None),
                            ProcedureVersion.effective_to > current,
                        ),
                    )
                )
            ).all()
        )
        query_terms = _terms(query)
        ranked: list[tuple[float, ProcedureMatch]] = []
        for procedure, version in rows:
            signals = list(
                await session.scalars(
                    select(ProcedureApplicability).where(
                        ProcedureApplicability.procedure_version_id == version.id
                    )
                )
            )
            steps = list(
                await session.scalars(
                    select(ProcedureStep)
                    .where(ProcedureStep.procedure_version_id == version.id)
                    .order_by(ProcedureStep.ordinal)
                )
            )
            tool_specs = [
                TOOL_REGISTRY.get(step.tool_name) for step in steps if step.tool_name is not None
            ]
            if any(spec is None for spec in tool_specs) or any(
                spec is not None and principal.role.value not in spec.allowed_roles
                for spec in tool_specs
            ):
                continue
            matched = tuple(
                f"{item.signal_type}:{item.signal_value}"
                for item in signals
                if item.signal_value.casefold() in query.casefold()
            )
            searchable = " ".join(
                [procedure.title, procedure.intent, procedure.description]
                + [item.signal_value for item in signals]
                + [item.action for item in steps]
            )
            overlap = len(query_terms.intersection(_terms(searchable))) / max(
                1, min(8, len(query_terms))
            )
            relevance = min(1.0, overlap + (0.3 if matched else 0))
            if relevance < 0.15:
                continue
            reliability = _wilson_lower(version.success_count, version.failure_count)
            content = self._render(procedure, version, steps)
            candidate = ContextCandidate(
                candidate_id=f"procedure:{version.id}",
                kind="procedural_memory",
                content=content,
                source_ref=f"procedure-version:{version.id}",
                scope=scope,
                relevance=relevance,
                importance=0.8,
                source_reliability=max(0.6, reliability),
                confidence=max(0.6, reliability),
                temporal_validity=1,
                task_utility=relevance,
                recency=0.8,
                token_cost=estimate_tokens(content),
                sensitivity="internal",
                provenance_refs=tuple(version.evidence_refs[:20]),
            )
            ranked.append(
                (
                    relevance * 0.7 + reliability * 0.3,
                    ProcedureMatch(version.id, candidate, matched),
                )
            )
        ranked.sort(key=lambda item: item[0], reverse=True)
        return tuple(item[1] for item in ranked[:limit])

    @staticmethod
    def _render(procedure: Procedure, version: ProcedureVersion, steps: list[ProcedureStep]) -> str:
        rendered = [
            f"Approved procedure {procedure.title} (version {version.version_number}).",
            "Use this only as a planning prior. Recheck live state, tool policy and approval.",
        ]
        for step in steps:
            tool = f" tool={step.tool_name}" if step.tool_name else ""
            approval = " approval_required=true" if step.approval_required else ""
            rendered.append(
                f"{step.ordinal + 1}. [{step.step_key}] {step.action}; "
                f"expect={step.expected_observation}{tool}{approval}"
            )
            if step.verification:
                rendered.append(f"   verify={step.verification}")
        return "\n".join(rendered)
