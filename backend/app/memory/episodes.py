"""Consolidate completed runs into owner-scoped episodic memory."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.context.builder import estimate_tokens
from app.agent.context.contracts import ContextCandidate, ContextScope
from app.agent.working_memory.contracts import WorkingMemorySnapshot
from app.db.models import (
    AgentRun,
    EpisodeAction,
    IncidentEpisode,
    Message,
    Ticket,
    ToolObservation,
    WorkingMemorySnapshotRecord,
)

_TOKEN = re.compile(r"[\w.-]+", re.UNICODE)
_ERROR = re.compile(r"\b(?:0x[0-9a-f]+|[A-Z][A-Z0-9_-]*-\d{2,}|\d{3,5})\b", re.IGNORECASE)


def _terms(value: str) -> set[str]:
    return {item.casefold() for item in _TOKEN.findall(value) if len(item) > 1}


def _detected_services(value: str) -> set[str]:
    normalized = value.casefold()
    return {item for item in ("vpn", "gitlab", "registry", "docker") if item in normalized}


class EpisodeMemoryService:
    async def consolidate(self, session: AsyncSession, *, run_id: UUID) -> IncidentEpisode | None:
        existing = await session.scalar(
            select(IncidentEpisode).where(IncidentEpisode.run_id == run_id)
        )
        if existing is not None:
            if existing.ticket_id is not None and not existing.verified:
                ticket = await session.get(Ticket, existing.ticket_id)
                if ticket is not None and ticket.status == "resolved":
                    existing.verified = True
                    existing.outcome = "resolved"
                    reference = f"ticket:{ticket.id}:resolved:v{ticket.version}"
                    existing.verification_refs = list(
                        dict.fromkeys([*existing.verification_refs, reference])
                    )
                    await session.flush()
            return existing
        run = await session.get(AgentRun, run_id)
        record = await session.scalar(
            select(WorkingMemorySnapshotRecord).where(WorkingMemorySnapshotRecord.run_id == run_id)
        )
        if run is None or record is None or run.finished_at is None:
            return None
        snapshot = WorkingMemorySnapshot.model_validate(record.snapshot)
        messages = list(
            await session.scalars(
                select(Message)
                .where(Message.run_id == run_id)
                .order_by(Message.created_at, Message.id)
            )
        )
        observations = list(
            await session.scalars(
                select(ToolObservation)
                .where(ToolObservation.run_id == run_id)
                .order_by(ToolObservation.created_at, ToolObservation.id)
            )
        )
        ticket = await session.get(Ticket, snapshot.ticket_id) if snapshot.ticket_id else None
        final = next((item.content for item in reversed(messages) if item.role == "assistant"), "")
        summary = f"Request: {snapshot.goal.statement}. Outcome: {final}"[:4000]
        verification_refs = [
            item.receipt_ref
            for item in observations
            if item.status == "success" and item.receipt_ref
        ]
        verified = bool(verification_refs) or bool(ticket and ticket.status == "resolved")
        outcome = (
            "ticket_created"
            if ticket
            else (
                "resolved"
                if run.outcome == "answered"
                else "cancelled"
                if run.outcome == "cancelled"
                else "unresolved"
            )
        )
        source_refs = [f"run:{run.id}", f"working-memory:{record.id}:v{record.version}"]
        if snapshot.plan.procedure_version_id is not None:
            source_refs.append(f"procedure-version:{snapshot.plan.procedure_version_id}")
        source_refs.extend(f"message:{item.id}" for item in messages)
        episode_services = set(snapshot.entities.service_ids)
        episode_services.update(_detected_services(snapshot.goal.statement + " " + final))
        if ticket is not None and ticket.issue_type != "other":
            episode_services.add(ticket.issue_type)
        episode = IncidentEpisode(
            run_id=run.id,
            owner_id=record.owner_id,
            conversation_id=record.conversation_id,
            device_id=snapshot.entities.device_id,
            ticket_id=ticket.id if ticket else None,
            summary=summary or "Completed support run",
            outcome=outcome,
            verified=verified,
            service_ids=sorted(episode_services),
            error_codes=sorted(set(_ERROR.findall(snapshot.goal.statement + " " + final)))[:20],
            source_refs=source_refs,
            verification_refs=[str(item) for item in verification_refs],
            started_at=run.created_at,
            completed_at=run.finished_at,
        )
        session.add(episode)
        await session.flush()
        session.add_all(
            EpisodeAction(
                episode_id=episode.id,
                ordinal=index,
                action_kind="tool",
                name=item.tool_name,
                status=item.status,
                summary=item.summary,
                receipt_ref=item.receipt_ref,
                source_ref=f"tool-observation:{item.id}",
                occurred_at=item.created_at,
            )
            for index, item in enumerate(observations)
        )
        await session.flush()
        return episode

    async def context_candidates(
        self,
        session: AsyncSession,
        *,
        owner_id: UUID,
        device_id: UUID | None,
        query: str,
        scope: ContextScope,
        limit: int = 3,
    ) -> tuple[ContextCandidate, ...]:
        statement = select(IncidentEpisode).where(
            IncidentEpisode.owner_id == owner_id,
            IncidentEpisode.deleted_at.is_(None),
        )
        if device_id is not None:
            statement = statement.where(
                (IncidentEpisode.device_id.is_(None)) | (IncidentEpisode.device_id == device_id)
            )
        rows = list(
            await session.scalars(statement.order_by(IncidentEpisode.completed_at.desc()).limit(50))
        )
        query_terms = _terms(query)
        ranked: list[tuple[float, IncidentEpisode]] = []
        for row in rows:
            overlap = len(query_terms.intersection(_terms(row.summary))) / max(
                1, min(8, len(query_terms))
            )
            service_match = any(item.casefold() in query.casefold() for item in row.service_ids)
            score = min(1.0, overlap + (0.25 if service_match else 0))
            if score > 0:
                ranked.append((score, row))
        ranked.sort(key=lambda item: (item[0], item[1].completed_at), reverse=True)
        return tuple(
            ContextCandidate(
                candidate_id=f"episode:{row.id}",
                kind="episodic_memory",
                content=(
                    f"Prior support episode ({row.outcome}, verified={row.verified}): {row.summary}"
                ),
                source_ref=f"incident-episode:{row.id}",
                scope=scope,
                relevance=score,
                importance=0.7 if row.verified else 0.5,
                source_reliability=0.9 if row.verified else 0.65,
                confidence=0.9 if row.verified else 0.65,
                temporal_validity=1,
                task_utility=score,
                recency=0.75,
                token_cost=estimate_tokens(row.summary),
                sensitivity="confidential",
                provenance_refs=tuple(row.source_refs[:20]),
            )
            for score, row in ranked[:limit]
        )
