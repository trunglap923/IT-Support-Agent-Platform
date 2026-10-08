"""Transactional registry and human review workflow for immutable procedures."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Document,
    DocumentVersion,
    DocumentVersionStatus,
    IncidentEpisode,
    Procedure,
    ProcedureApplicability,
    ProcedureReview,
    ProcedureStep,
    ProcedureVersion,
)
from app.procedures.contracts import ProcedureCandidateDefinition, ProcedureReviewDecision
from app.procedures.validation import ProcedureSandboxValidator
from app.tools.registry import TOOL_REGISTRY


class ProcedureNotFoundError(LookupError):
    pass


class ProcedureConflictError(RuntimeError):
    pass


class ProcedureRegistryService:
    async def create_candidate(
        self,
        session: AsyncSession,
        *,
        definition: ProcedureCandidateDefinition,
        created_by: UUID | None,
        technician_authored: bool,
    ) -> ProcedureVersion:
        await self._validate_evidence(
            session, definition=definition, technician_authored=technician_authored
        )
        self._validate_steps(definition)
        visibility, department_id = await self._validated_visibility(session, definition)
        procedure = await session.scalar(
            select(Procedure).where(Procedure.key == definition.key).with_for_update()
        )
        if procedure is None:
            procedure = Procedure(
                key=definition.key,
                title=definition.title.strip(),
                intent=definition.intent.strip().casefold(),
                description=definition.description.strip(),
            )
            session.add(procedure)
            await session.flush()
        else:
            duplicate = await session.scalar(
                select(ProcedureVersion).where(
                    ProcedureVersion.procedure_id == procedure.id,
                    ProcedureVersion.compiled_signature == definition.compiled_signature,
                    ProcedureVersion.status.in_(("candidate", "review", "approved")),
                )
            )
            if duplicate is not None:
                return duplicate
            procedure.title = definition.title.strip()
            procedure.intent = definition.intent.strip().casefold()
            procedure.description = definition.description.strip()
            procedure.version += 1
        latest = await session.scalar(
            select(func.max(ProcedureVersion.version_number)).where(
                ProcedureVersion.procedure_id == procedure.id
            )
        )
        version = ProcedureVersion(
            procedure_id=procedure.id,
            version_number=int(latest or 0) + 1,
            status="candidate",
            visibility=visibility,
            department_id=department_id,
            version_range=definition.version_range,
            prerequisites=list(definition.prerequisites),
            prohibited_actions=list(definition.prohibited_actions),
            evidence_refs=list(definition.evidence_refs),
            example_episode_ids=[str(item) for item in definition.example_episode_ids],
            source_document_version_id=definition.source_document_version_id,
            compiled_signature=definition.compiled_signature,
            created_by=created_by,
        )
        session.add(version)
        await session.flush()
        session.add_all(
            ProcedureApplicability(
                procedure_version_id=version.id,
                signal_type=item.signal_type,
                signal_value=item.value,
            )
            for item in definition.applicability
        )
        session.add_all(
            ProcedureStep(
                procedure_version_id=version.id,
                ordinal=index,
                step_key=item.step_key,
                action=" ".join(item.action.split()),
                tool_name=item.tool_name,
                expected_observation=" ".join(item.expected_observation.split()),
                on_success=item.on_success,
                on_failure=item.on_failure,
                permission=item.permission,
                approval_required=item.approval_required,
                verification=(" ".join(item.verification.split()) if item.verification else None),
            )
            for index, item in enumerate(definition.steps)
        )
        await session.flush()
        return version

    async def submit_for_review(
        self, session: AsyncSession, *, version_id: UUID
    ) -> ProcedureVersion:
        version = await self._locked_version(session, version_id)
        if version.status == "review":
            return version
        if version.status != "candidate":
            raise ProcedureConflictError("Only a candidate procedure can enter review")
        version.status = "review"
        await session.flush()
        return version

    async def review(
        self,
        session: AsyncSession,
        *,
        version_id: UUID,
        reviewer_id: UUID,
        review: ProcedureReviewDecision,
        now: datetime | None = None,
    ) -> ProcedureVersion:
        current = now or datetime.now(UTC)
        version = await self._locked_version(session, version_id)
        procedure = await session.scalar(
            select(Procedure).where(Procedure.id == version.procedure_id).with_for_update()
        )
        if procedure is None:
            raise ProcedureNotFoundError("Procedure not found")
        if review.decision == "approve":
            if version.status != "review":
                raise ProcedureConflictError("Only a version under review can be approved")
            await self._validate_source_is_current(session, version)
            await self._validate_publish_evidence(session, version)
            await self._validate_version_steps(session, version)
            if procedure.current_version_id is not None:
                previous = await session.get(ProcedureVersion, procedure.current_version_id)
                if previous is not None and previous.id != version.id:
                    previous.status = "deprecated"
                    previous.effective_to = current
            version.status = "approved"
            version.approved_by = reviewer_id
            version.reviewed_at = current
            version.effective_from = current
            version.effective_to = None
            version.last_validated_at = current
            procedure.current_version_id = version.id
        elif review.decision == "reject":
            if version.status not in {"candidate", "review"}:
                raise ProcedureConflictError("Published versions cannot be rejected")
            version.status = "rejected"
            version.reviewed_at = current
        elif review.decision == "request_changes":
            if version.status != "review":
                raise ProcedureConflictError("Only a version under review can request changes")
            version.status = "candidate"
            version.reviewed_at = current
        else:
            if version.status != "approved":
                raise ProcedureConflictError("Only an approved version can be deprecated")
            version.status = "deprecated"
            version.effective_to = current
            version.reviewed_at = current
            if procedure.current_version_id == version.id:
                procedure.current_version_id = None
        session.add(
            ProcedureReview(
                procedure_version_id=version.id,
                reviewer_id=reviewer_id,
                decision=review.decision,
                notes=(review.notes or "").strip()[:1000] or None,
            )
        )
        await session.flush()
        return version

    async def stale_versions(self, session: AsyncSession) -> list[ProcedureVersion]:
        return list(
            await session.scalars(
                select(ProcedureVersion)
                .join(
                    DocumentVersion,
                    DocumentVersion.id == ProcedureVersion.source_document_version_id,
                )
                .join(Document, Document.id == DocumentVersion.document_id)
                .where(
                    ProcedureVersion.status.in_(("candidate", "review", "approved")),
                    (Document.current_version_id != DocumentVersion.id)
                    | (DocumentVersion.status != DocumentVersionStatus.PUBLISHED),
                )
                .order_by(ProcedureVersion.created_at)
            )
        )

    @staticmethod
    def _validate_steps(definition: ProcedureCandidateDefinition) -> None:
        for step in definition.steps:
            if step.tool_name is None:
                if step.approval_required:
                    raise ProcedureConflictError("Manual steps cannot claim tool approval")
                continue
            spec = TOOL_REGISTRY.get(step.tool_name)
            if spec is None:
                raise ProcedureConflictError("Procedure references an unknown tool")
            required = spec.approval_policy == "always"
            if step.approval_required != required:
                raise ProcedureConflictError("Procedure approval metadata differs from tool policy")

    async def _validate_evidence(
        self,
        session: AsyncSession,
        *,
        definition: ProcedureCandidateDefinition,
        technician_authored: bool,
    ) -> None:
        if definition.source_document_version_id is not None:
            version = await session.get(DocumentVersion, definition.source_document_version_id)
            if version is None or version.status is not DocumentVersionStatus.PUBLISHED:
                raise ProcedureConflictError("Source runbook version must be published")
        if not definition.example_episode_ids:
            if not technician_authored or definition.source_document_version_id is None:
                raise ProcedureConflictError(
                    "A technician-authored procedure requires a published runbook source"
                )
            return
        episodes = list(
            await session.scalars(
                select(IncidentEpisode).where(
                    IncidentEpisode.id.in_(definition.example_episode_ids),
                    IncidentEpisode.deleted_at.is_(None),
                )
            )
        )
        if len(episodes) != len(set(definition.example_episode_ids)) or any(
            not item.verified for item in episodes
        ):
            raise ProcedureConflictError("Procedure episodes must exist and be verified")
        if len(episodes) < 2 and not technician_authored:
            raise ProcedureConflictError("Automatic compilation requires two verified episodes")

    async def _validate_source_is_current(
        self, session: AsyncSession, version: ProcedureVersion
    ) -> None:
        if version.source_document_version_id is None:
            return
        source = await session.get(DocumentVersion, version.source_document_version_id)
        document = await session.get(Document, source.document_id) if source else None
        if (
            source is None
            or document is None
            or document.archived
            or source.status is not DocumentVersionStatus.PUBLISHED
            or document.current_version_id != source.id
        ):
            raise ProcedureConflictError("Procedure source runbook is no longer current")

    async def _validate_publish_evidence(
        self, session: AsyncSession, version: ProcedureVersion
    ) -> None:
        if not version.example_episode_ids:
            if version.source_document_version_id is None:
                raise ProcedureConflictError("Procedure has no resolvable publication evidence")
            return
        try:
            episode_ids = [UUID(item) for item in version.example_episode_ids]
        except ValueError as error:
            raise ProcedureConflictError("Procedure episode evidence is malformed") from error
        episodes = list(
            await session.scalars(
                select(IncidentEpisode).where(
                    IncidentEpisode.id.in_(episode_ids),
                    IncidentEpisode.verified.is_(True),
                    IncidentEpisode.deleted_at.is_(None),
                )
            )
        )
        if len(episodes) != len(set(episode_ids)):
            raise ProcedureConflictError("Procedure episode evidence is no longer valid")

    async def _validate_version_steps(
        self, session: AsyncSession, version: ProcedureVersion
    ) -> None:
        steps = list(
            await session.scalars(
                select(ProcedureStep).where(ProcedureStep.procedure_version_id == version.id)
            )
        )
        report = ProcedureSandboxValidator().validate(steps)
        version.validation_report = report.as_dict()
        if not report.passed:
            raise ProcedureConflictError("Procedure failed deterministic sandbox validation")

    async def _validated_visibility(
        self, session: AsyncSession, definition: ProcedureCandidateDefinition
    ) -> tuple[str, UUID | None]:
        if definition.source_document_version_id is None:
            return definition.visibility, definition.department_id
        source = await session.get(DocumentVersion, definition.source_document_version_id)
        document = await session.get(Document, source.document_id) if source else None
        if source is None or document is None:
            raise ProcedureConflictError("Source runbook was not found")
        rank = {"company": 0, "department": 1, "it_only": 2}
        source_visibility = document.visibility.value
        if rank[definition.visibility] < rank[source_visibility]:
            raise ProcedureConflictError("Procedure visibility cannot exceed its source runbook")
        if (
            source_visibility == "department"
            and definition.visibility == "department"
            and definition.department_id != document.department_id
        ):
            raise ProcedureConflictError("Procedure department must match its source runbook")
        return definition.visibility, definition.department_id

    @staticmethod
    async def _locked_version(session: AsyncSession, version_id: UUID) -> ProcedureVersion:
        version = await session.scalar(
            select(ProcedureVersion).where(ProcedureVersion.id == version_id).with_for_update()
        )
        if version is None:
            raise ProcedureNotFoundError("Procedure version not found")
        return version
