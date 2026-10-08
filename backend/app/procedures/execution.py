"""Pin procedure versions to runs and record verified operational feedback."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ProcedureExecution,
    ProcedureStep,
    ProcedureVersion,
    Ticket,
    ToolObservation,
)


class ProcedureExecutionService:
    async def start(
        self,
        session: AsyncSession,
        *,
        procedure_version_id: UUID,
        run_id: UUID,
        owner_id: UUID,
        matched_signals: tuple[str, ...],
        now: datetime | None = None,
    ) -> ProcedureExecution:
        existing = await session.scalar(
            select(ProcedureExecution).where(
                ProcedureExecution.procedure_version_id == procedure_version_id,
                ProcedureExecution.run_id == run_id,
            )
        )
        if existing is not None:
            return existing
        version = await session.scalar(
            select(ProcedureVersion).where(
                ProcedureVersion.id == procedure_version_id,
                ProcedureVersion.status == "approved",
            )
        )
        if version is None:
            raise LookupError("Approved procedure version not found")
        execution = ProcedureExecution(
            procedure_version_id=procedure_version_id,
            run_id=run_id,
            owner_id=owner_id,
            matched_signals=list(matched_signals),
            started_at=now or datetime.now(UTC),
        )
        session.add(execution)
        await session.flush()
        return execution

    async def complete_for_run(
        self,
        session: AsyncSession,
        *,
        run_id: UUID,
        owner_id: UUID,
        run_outcome: str,
        ticket_id: UUID | None,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(UTC)
        executions = list(
            await session.scalars(
                select(ProcedureExecution)
                .where(
                    ProcedureExecution.run_id == run_id,
                    ProcedureExecution.owner_id == owner_id,
                    ProcedureExecution.status == "running",
                )
                .with_for_update()
            )
        )
        if not executions:
            return
        observations = list(
            await session.scalars(
                select(ToolObservation)
                .where(ToolObservation.run_id == run_id)
                .order_by(ToolObservation.created_at, ToolObservation.id)
            )
        )
        ticket = await session.get(Ticket, ticket_id) if ticket_id else None
        for execution in executions:
            steps = list(
                await session.scalars(
                    select(ProcedureStep)
                    .where(ProcedureStep.procedure_version_id == execution.procedure_version_id)
                    .order_by(ProcedureStep.ordinal)
                )
            )
            step_by_tool = {
                step.tool_name: step.step_key for step in steps if step.tool_name is not None
            }
            relevant_observations = [
                item for item in observations if item.tool_name in step_by_tool
            ]
            attempted = [step_by_tool[item.tool_name] for item in relevant_observations]
            successful_steps = {
                step_by_tool[item.tool_name]
                for item in relevant_observations
                if item.status == "success"
            }
            required_tool_steps = set(step_by_tool.values())
            receipt_refs = [
                item.receipt_ref
                for item in relevant_observations
                if item.status == "success" and item.receipt_ref
            ]
            verified = bool(ticket and ticket.status == "resolved") or bool(
                receipt_refs and required_tool_steps.issubset(successful_steps)
            )
            if verified and run_outcome in {"answered", "ticket_created"}:
                outcome = "success"
            elif any(item.status == "failed" for item in relevant_observations) or (
                run_outcome not in {"answered", "needs_information"}
            ):
                outcome = "failure"
            else:
                outcome = "abandoned"
            execution.status = "completed"
            execution.outcome = outcome
            execution.verified = verified
            execution.ticket_id = ticket_id
            execution.attempted_step_keys = list(dict.fromkeys(attempted))
            execution.receipt_refs = [str(item) for item in receipt_refs]
            execution.completed_at = current
            version = await session.scalar(
                select(ProcedureVersion)
                .where(ProcedureVersion.id == execution.procedure_version_id)
                .with_for_update()
            )
            if version is not None:
                if outcome == "success" and verified:
                    version.success_count += 1
                    version.last_validated_at = current
                elif outcome == "failure":
                    version.failure_count += 1
        await session.flush()
