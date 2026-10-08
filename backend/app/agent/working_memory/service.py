"""Transactional durable working-memory lifecycle shared by runtime adapters."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.working_memory.contracts import (
    NormalizedToolObservation,
    PendingAction,
    VerificationRequirement,
    WorkingCompactionState,
    WorkingCounters,
    WorkingEntities,
    WorkingGoal,
    WorkingMemorySnapshot,
    WorkingMemoryStatus,
    WorkingObservation,
    WorkingPlan,
    WorkingPlanStep,
)
from app.db.models import (
    ToolObservation,
    WorkingMemoryEvent,
    WorkingMemorySnapshotRecord,
)

ALLOWED_WORKING_MEMORY_TRANSITIONS: dict[WorkingMemoryStatus, frozenset[WorkingMemoryStatus]] = {
    "active": frozenset(
        {"waiting_input", "waiting_approval", "verifying", "completed", "failed", "cancelled"}
    ),
    "waiting_input": frozenset({"active", "cancelled", "failed"}),
    "waiting_approval": frozenset({"active", "cancelled", "failed"}),
    "verifying": frozenset({"active", "completed", "failed", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}

SnapshotTransform = Callable[[WorkingMemorySnapshot, int, datetime], WorkingMemorySnapshot]


class WorkingMemoryNotFoundError(LookupError):
    pass


class WorkingMemoryVersionConflictError(RuntimeError):
    pass


class InvalidWorkingMemoryTransitionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WorkingMemoryOperationResult:
    snapshot: WorkingMemorySnapshot
    event: WorkingMemoryEvent
    applied: bool


def validate_working_memory_transition(
    current: WorkingMemoryStatus, target: WorkingMemoryStatus
) -> None:
    if target not in ALLOWED_WORKING_MEMORY_TRANSITIONS[current]:
        raise InvalidWorkingMemoryTransitionError(
            f"Cannot transition working memory from {current} to {target}"
        )


def _bounded(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    return normalized[:limit] or "Support request"


def _reconcile_counters(
    current: WorkingCounters, supplied: WorkingCounters | None
) -> WorkingCounters:
    if supplied is None:
        return current
    return WorkingCounters(
        model_calls=max(current.model_calls, supplied.model_calls),
        tool_calls=max(current.tool_calls, supplied.tool_calls),
        retrieval_calls=max(current.retrieval_calls, supplied.retrieval_calls),
    )


class WorkingMemoryService:
    async def load(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        owner_id: UUID,
        for_update: bool = False,
    ) -> WorkingMemorySnapshot | None:
        statement = select(WorkingMemorySnapshotRecord).where(
            WorkingMemorySnapshotRecord.run_id == run_id
        )
        statement = statement.where(WorkingMemorySnapshotRecord.owner_id == owner_id)
        if for_update:
            statement = statement.with_for_update()
        record = cast(WorkingMemorySnapshotRecord | None, await session.scalar(statement))
        return self._snapshot(record) if record is not None else None

    async def create_or_load(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        conversation_id: UUID,
        owner_id: UUID,
        current_message_id: UUID,
        query: str,
        device_id: UUID | None,
        now: datetime | None = None,
    ) -> WorkingMemorySnapshot:
        existing = await self.load(session, run_id=run_id, owner_id=owner_id, for_update=True)
        if existing is not None:
            return existing
        timestamp = now or datetime.now(UTC)
        memory_id = uuid4()
        snapshot = WorkingMemorySnapshot(
            working_memory_id=memory_id,
            run_id=run_id,
            conversation_id=conversation_id,
            owner_id=owner_id,
            status="active",
            goal=WorkingGoal(
                statement=_bounded(query, 1_000),
                success_criteria=("Produce and persist a policy-compliant support outcome.",),
                constraints=("Do not treat memory as authorization.",),
            ),
            entities=WorkingEntities(user_id=owner_id, device_id=device_id),
            plan=WorkingPlan(
                version=1,
                steps=(
                    WorkingPlanStep(
                        step_id="analyze-request",
                        title="Analyze the latest support request",
                        kind="inspect",
                        status="running",
                    ),
                    WorkingPlanStep(
                        step_id="respond-to-user",
                        title="Return a verified support outcome",
                        kind="communicate",
                        depends_on=("analyze-request",),
                    ),
                ),
            ),
            observations=(
                WorkingObservation(
                    observation_id=f"message:{current_message_id}",
                    source_type="user",
                    source_ref=f"message:{current_message_id}",
                    summary=_bounded(query, 2_000),
                    observed_at=timestamp,
                    reliability=1.0,
                ),
            ),
            verification_requirements=(
                VerificationRequirement(
                    requirement_id="final-outcome-persisted",
                    statement="The final outcome and relevant evidence are persisted.",
                ),
            ),
            version=1,
            created_at=timestamp,
            updated_at=timestamp,
        )
        record = WorkingMemorySnapshotRecord(
            id=memory_id,
            run_id=run_id,
            conversation_id=conversation_id,
            owner_id=owner_id,
            status=snapshot.status,
            schema_version=snapshot.schema_version,
            snapshot=snapshot.model_dump(mode="json"),
            event_sequence=1,
            version=1,
            created_at=timestamp,
            updated_at=timestamp,
        )
        event = WorkingMemoryEvent(
            working_memory_id=memory_id,
            run_id=run_id,
            sequence=1,
            event_type="created",
            operation_id=f"working-memory-create:{run_id}",
            from_status=None,
            to_status="active",
            snapshot_version=1,
            safe_payload={"source_message_id": str(current_message_id)},
            created_at=timestamp,
        )
        session.add_all([record, event])
        await session.flush()
        return snapshot

    async def bind_procedure(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        owner_id: UUID,
        procedure_version_id: UUID,
    ) -> WorkingMemoryOperationResult:
        """Pin one immutable approved procedure version to the active run plan."""

        record = await self._record_for_update(session, run_id=run_id, owner_id=owner_id)

        def transform(
            snapshot: WorkingMemorySnapshot, sequence: int, timestamp: datetime
        ) -> WorkingMemorySnapshot:
            del sequence, timestamp
            if snapshot.plan.procedure_version_id not in {None, procedure_version_id}:
                raise WorkingMemoryVersionConflictError(
                    "A different procedure version is already pinned to this run"
                )
            return snapshot.model_copy(
                update={
                    "plan": snapshot.plan.model_copy(
                        update={
                            "version": snapshot.plan.version + 1,
                            "procedure_version_id": procedure_version_id,
                        }
                    )
                }
            )

        return await self._apply(
            session,
            record=record,
            operation_id=f"working-memory-bind-procedure:{run_id}:{procedure_version_id}",
            event_type="procedure_bound",
            expected_version=None,
            transform=transform,
            safe_payload={"procedure_version_id": str(procedure_version_id)},
        )

    async def apply_transition(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        owner_id: UUID,
        target: WorkingMemoryStatus,
        operation_id: str,
        safe_payload: dict[str, Any] | None = None,
        counters: WorkingCounters | None = None,
        expected_version: int | None = None,
    ) -> WorkingMemoryOperationResult:
        """Apply a status-only transition for waiting-input, verification or cancellation."""

        if target in {"waiting_approval", "completed", "failed"}:
            raise ValueError("Use the specialized working-memory lifecycle method")
        record = await self._record_for_update(session, run_id=run_id, owner_id=owner_id)

        def transform(
            snapshot: WorkingMemorySnapshot, sequence: int, timestamp: datetime
        ) -> WorkingMemorySnapshot:
            del sequence, timestamp
            validate_working_memory_transition(snapshot.status, target)
            updates: dict[str, Any] = {
                "status": target,
                "counters": _reconcile_counters(snapshot.counters, counters),
            }
            if target == "cancelled":
                steps = tuple(
                    step.model_copy(update={"status": "skipped"})
                    if step.status in {"pending", "running", "blocked"}
                    else step
                    for step in snapshot.plan.steps
                )
                updates.update(
                    plan=snapshot.plan.model_copy(
                        update={"version": snapshot.plan.version + 1, "steps": steps}
                    ),
                    pending_actions=(),
                )
            return snapshot.model_copy(update=updates)

        return await self._apply(
            session,
            record=record,
            operation_id=operation_id,
            event_type="status_changed",
            expected_version=expected_version,
            transform=transform,
            safe_payload={"target": target, **(safe_payload or {})},
        )

    async def record_observation(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        owner_id: UUID,
        observation: NormalizedToolObservation,
        expected_version: int | None = None,
    ) -> WorkingMemoryOperationResult:
        record = await self._record_for_update(session, run_id=run_id, owner_id=owner_id)
        existing = await session.scalar(
            select(ToolObservation).where(
                ToolObservation.run_id == run_id,
                ToolObservation.call_id == observation.call_id,
            )
        )
        if existing is not None:
            event = await self._event_by_operation(
                session,
                working_memory_id=record.id,
                operation_id=f"tool-observation:{observation.call_id}",
            )
            if event is None:
                raise RuntimeError("Tool observation exists without its working-memory event")
            return WorkingMemoryOperationResult(
                snapshot=self._snapshot(record), event=event, applied=False
            )

        observation_id = uuid4()
        session.add(
            ToolObservation(
                id=observation_id,
                working_memory_id=record.id,
                run_id=run_id,
                owner_id=owner_id,
                call_id=observation.call_id,
                tool_name=observation.tool_name,
                status=observation.status,
                error_code=observation.error_code,
                summary=observation.summary,
                arguments_hash=observation.arguments_hash,
                result_hash=observation.result_hash,
                artifact_ref=observation.artifact_ref,
                receipt_ref=observation.receipt_ref,
                safe_metadata=observation.safe_metadata,
                schema_version=observation.schema_version,
                created_at=observation.observed_at,
            )
        )
        step_id = f"tool-{hashlib.sha256(observation.call_id.encode()).hexdigest()[:12]}"

        def transform(
            snapshot: WorkingMemorySnapshot, sequence: int, timestamp: datetime
        ) -> WorkingMemorySnapshot:
            del timestamp
            new_item = WorkingObservation(
                observation_id=f"tool:{observation_id}",
                source_type="tool",
                source_ref=f"tool_call:{observation.call_id}",
                summary=observation.summary,
                raw_artifact_ref=f"tool_observation:{observation_id}",
                observed_at=observation.observed_at,
                reliability=observation.reliability,
            )
            observations = [*snapshot.observations, new_item]
            compaction = snapshot.compaction
            if len(observations) > 100:
                removed = observations[:-100]
                observations = observations[-100:]
                source_ids = [
                    *compaction.source_event_ids,
                    *(item.observation_id for item in removed),
                ][-200:]
                compaction = WorkingCompactionState(
                    last_compacted_event_sequence=sequence,
                    summary_version=compaction.summary_version + 1,
                    summary=f"{len(removed)} older observation(s) compacted; raw records retained.",
                    source_event_ids=tuple(source_ids),
                )
            steps = [
                step.model_copy(update={"status": "succeeded"})
                if step.step_id == "analyze-request" and step.status == "running"
                else step
                for step in snapshot.plan.steps
            ]
            if all(step.step_id != step_id for step in steps):
                steps.append(
                    WorkingPlanStep(
                        step_id=step_id,
                        title=f"Execute {observation.tool_name}",
                        kind=(
                            "retrieve"
                            if observation.tool_name == "search_knowledge_base"
                            else "inspect"
                        ),
                        status="succeeded" if observation.status == "success" else "failed",
                        depends_on=("analyze-request",),
                        tool_name=observation.tool_name,
                    )
                )
            counters = WorkingCounters(
                model_calls=snapshot.counters.model_calls,
                tool_calls=snapshot.counters.tool_calls + 1,
                retrieval_calls=snapshot.counters.retrieval_calls
                + int(observation.tool_name == "search_knowledge_base"),
            )
            return snapshot.model_copy(
                update={
                    "observations": tuple(observations),
                    "compaction": compaction,
                    "plan": snapshot.plan.model_copy(
                        update={"version": snapshot.plan.version + 1, "steps": tuple(steps)}
                    ),
                    "counters": counters,
                }
            )

        return await self._apply(
            session,
            record=record,
            operation_id=f"tool-observation:{observation.call_id}",
            event_type="observation_recorded",
            expected_version=expected_version,
            transform=transform,
            safe_payload={
                "observation_id": str(observation_id),
                "tool_name": observation.tool_name,
                "status": observation.status,
                "error_code": observation.error_code,
            },
        )

    async def pause(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        owner_id: UUID,
        action_id: str,
        tool_name: str,
        arguments_hash: str,
        counters: WorkingCounters | None = None,
        expected_version: int | None = None,
    ) -> WorkingMemoryOperationResult:
        record = await self._record_for_update(session, run_id=run_id, owner_id=owner_id)

        def transform(
            snapshot: WorkingMemorySnapshot, sequence: int, timestamp: datetime
        ) -> WorkingMemorySnapshot:
            del sequence, timestamp
            validate_working_memory_transition(snapshot.status, "waiting_approval")
            step_id = f"approval-{hashlib.sha256(action_id.encode()).hexdigest()[:12]}"
            steps = [
                step.model_copy(update={"status": "succeeded"})
                if step.step_id in {"analyze-request", "respond-to-user"}
                and step.status in {"pending", "running"}
                else step
                for step in snapshot.plan.steps
            ]
            if all(step.step_id != step_id for step in steps):
                steps.append(
                    WorkingPlanStep(
                        step_id=step_id,
                        title=f"Await approval for {tool_name}",
                        kind="action",
                        status="blocked",
                        depends_on=("analyze-request",),
                        tool_name=tool_name,
                        requires_approval=True,
                    )
                )
            return snapshot.model_copy(
                update={
                    "status": "waiting_approval",
                    "plan": snapshot.plan.model_copy(
                        update={"version": snapshot.plan.version + 1, "steps": tuple(steps)}
                    ),
                    "pending_actions": (
                        PendingAction(
                            action_id=action_id,
                            plan_step_id=step_id,
                            tool_name=tool_name,
                            arguments_hash=arguments_hash,
                            requires_approval=True,
                        ),
                    ),
                    "counters": _reconcile_counters(snapshot.counters, counters),
                }
            )

        return await self._apply(
            session,
            record=record,
            operation_id=f"working-memory-pause:{action_id}",
            event_type="paused",
            expected_version=expected_version,
            transform=transform,
            safe_payload={"action_id": action_id, "tool_name": tool_name},
        )

    async def resume(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        owner_id: UUID,
        action_id: str,
        approved: bool,
        expected_version: int | None = None,
    ) -> WorkingMemoryOperationResult:
        record = await self._record_for_update(session, run_id=run_id, owner_id=owner_id)

        def transform(
            snapshot: WorkingMemorySnapshot, sequence: int, timestamp: datetime
        ) -> WorkingMemorySnapshot:
            del sequence, timestamp
            validate_working_memory_transition(snapshot.status, "active")
            action = next(
                (item for item in snapshot.pending_actions if item.action_id == action_id), None
            )
            if action is None:
                raise ValueError("Pending working-memory action was not found")
            steps = tuple(
                step.model_copy(update={"status": "succeeded" if approved else "skipped"})
                if step.step_id == action.plan_step_id
                else step
                for step in snapshot.plan.steps
            )
            return snapshot.model_copy(
                update={
                    "status": "active",
                    "plan": snapshot.plan.model_copy(
                        update={"version": snapshot.plan.version + 1, "steps": steps}
                    ),
                    "pending_actions": tuple(
                        item for item in snapshot.pending_actions if item.action_id != action_id
                    ),
                }
            )

        return await self._apply(
            session,
            record=record,
            operation_id=f"working-memory-resume:{action_id}",
            event_type="resumed",
            expected_version=expected_version,
            transform=transform,
            safe_payload={"action_id": action_id, "approved": approved},
        )

    async def complete(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        owner_id: UUID,
        operation_id: str,
        outcome: str,
        counters: WorkingCounters | None = None,
        ticket_id: UUID | None = None,
        expected_version: int | None = None,
    ) -> WorkingMemoryOperationResult:
        record = await self._record_for_update(session, run_id=run_id, owner_id=owner_id)

        def transform(
            snapshot: WorkingMemorySnapshot, sequence: int, timestamp: datetime
        ) -> WorkingMemorySnapshot:
            del sequence, timestamp
            validate_working_memory_transition(snapshot.status, "completed")
            steps = tuple(
                step.model_copy(update={"status": "succeeded"})
                if step.step_id in {"analyze-request", "respond-to-user"}
                and step.status in {"pending", "running"}
                else step
                for step in snapshot.plan.steps
            )
            requirements = tuple(
                requirement.model_copy(update={"status": "satisfied"})
                for requirement in snapshot.verification_requirements
            )
            return snapshot.model_copy(
                update={
                    "status": "completed",
                    "ticket_id": ticket_id or snapshot.ticket_id,
                    "plan": snapshot.plan.model_copy(
                        update={"version": snapshot.plan.version + 1, "steps": steps}
                    ),
                    "pending_actions": (),
                    "verification_requirements": requirements,
                    "counters": _reconcile_counters(snapshot.counters, counters),
                }
            )

        return await self._apply(
            session,
            record=record,
            operation_id=operation_id,
            event_type="completed",
            expected_version=expected_version,
            transform=transform,
            safe_payload={"outcome": outcome, "ticket_id": str(ticket_id) if ticket_id else None},
        )

    async def fail(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        owner_id: UUID,
        operation_id: str,
        error_code: str,
        expected_version: int | None = None,
    ) -> WorkingMemoryOperationResult:
        record = await self._record_for_update(session, run_id=run_id, owner_id=owner_id)

        def transform(
            snapshot: WorkingMemorySnapshot, sequence: int, timestamp: datetime
        ) -> WorkingMemorySnapshot:
            del sequence, timestamp
            validate_working_memory_transition(snapshot.status, "failed")
            steps = tuple(
                step.model_copy(update={"status": "failed"}) if step.status == "running" else step
                for step in snapshot.plan.steps
            )
            return snapshot.model_copy(
                update={
                    "status": "failed",
                    "plan": snapshot.plan.model_copy(
                        update={"version": snapshot.plan.version + 1, "steps": steps}
                    ),
                    "pending_actions": (),
                }
            )

        return await self._apply(
            session,
            record=record,
            operation_id=operation_id,
            event_type="failed",
            expected_version=expected_version,
            transform=transform,
            safe_payload={"error_code": error_code},
        )

    async def _apply(
        self,
        session: AsyncSession,
        *,
        record: WorkingMemorySnapshotRecord,
        operation_id: str,
        event_type: str,
        expected_version: int | None,
        transform: SnapshotTransform,
        safe_payload: dict[str, Any],
    ) -> WorkingMemoryOperationResult:
        existing = await self._event_by_operation(
            session, working_memory_id=record.id, operation_id=operation_id
        )
        if existing is not None:
            return WorkingMemoryOperationResult(
                snapshot=self._snapshot(record), event=existing, applied=False
            )
        if expected_version is not None and record.version != expected_version:
            raise WorkingMemoryVersionConflictError("Working-memory version is stale")
        current = self._snapshot(record)
        if current.version != record.version:
            raise WorkingMemoryVersionConflictError("Snapshot payload version is inconsistent")
        timestamp = datetime.now(UTC)
        next_sequence = record.event_sequence + 1
        next_version = record.version + 1
        candidate = transform(current, next_sequence, timestamp).model_copy(
            update={"version": next_version, "updated_at": timestamp}
        )
        updated = WorkingMemorySnapshot.model_validate(candidate.model_dump(mode="python"))
        event = WorkingMemoryEvent(
            working_memory_id=record.id,
            run_id=record.run_id,
            sequence=next_sequence,
            event_type=event_type,
            operation_id=operation_id,
            from_status=current.status,
            to_status=updated.status,
            snapshot_version=next_version,
            safe_payload=safe_payload,
            created_at=timestamp,
        )
        mutation = cast(
            CursorResult[Any],
            await session.execute(
                update(WorkingMemorySnapshotRecord)
                .where(
                    WorkingMemorySnapshotRecord.id == record.id,
                    WorkingMemorySnapshotRecord.version == record.version,
                )
                .values(
                    status=updated.status,
                    ticket_id=updated.ticket_id,
                    incident_key=updated.incident_key,
                    snapshot=updated.model_dump(mode="json"),
                    event_sequence=next_sequence,
                    version=next_version,
                    updated_at=timestamp,
                )
            ),
        )
        if mutation.rowcount != 1:
            raise WorkingMemoryVersionConflictError("Working-memory update lost a version race")
        session.add(event)
        await session.flush()
        return WorkingMemoryOperationResult(snapshot=updated, event=event, applied=True)

    async def _record_for_update(
        self, session: AsyncSession, *, run_id: UUID, owner_id: UUID
    ) -> WorkingMemorySnapshotRecord:
        record = cast(
            WorkingMemorySnapshotRecord | None,
            await session.scalar(
                select(WorkingMemorySnapshotRecord)
                .where(
                    WorkingMemorySnapshotRecord.run_id == run_id,
                    WorkingMemorySnapshotRecord.owner_id == owner_id,
                )
                .with_for_update()
            ),
        )
        if record is None:
            raise WorkingMemoryNotFoundError("Working memory was not found")
        return record

    @staticmethod
    async def _event_by_operation(
        session: AsyncSession, *, working_memory_id: UUID, operation_id: str
    ) -> WorkingMemoryEvent | None:
        return cast(
            WorkingMemoryEvent | None,
            await session.scalar(
                select(WorkingMemoryEvent).where(
                    WorkingMemoryEvent.working_memory_id == working_memory_id,
                    WorkingMemoryEvent.operation_id == operation_id,
                )
            ),
        )

    @staticmethod
    def _snapshot(record: WorkingMemorySnapshotRecord) -> WorkingMemorySnapshot:
        return WorkingMemorySnapshot.model_validate(record.snapshot)
