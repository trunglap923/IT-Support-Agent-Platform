"""Deterministic candidate compiler for repeated, verified support episodes."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EpisodeAction, IncidentEpisode, ProcedureVersion
from app.procedures.contracts import (
    ApplicabilitySignal,
    ProcedureCandidateDefinition,
    ProcedureStepDefinition,
)
from app.procedures.registry import ProcedureRegistryService
from app.tools.registry import TOOL_REGISTRY

_KEY = re.compile(r"[^A-Z0-9]+")


class ProcedureCompiler:
    """Compile de-identified candidates only when repeated verified traces agree."""

    async def compile_verified_episodes(
        self, session: AsyncSession, *, minimum_examples: int = 2, limit: int = 500
    ) -> int:
        episodes = list(
            await session.scalars(
                select(IncidentEpisode)
                .where(
                    IncidentEpisode.verified.is_(True),
                    IncidentEpisode.deleted_at.is_(None),
                )
                .order_by(IncidentEpisode.completed_at.desc())
                .limit(limit)
            )
        )
        groups: dict[tuple[tuple[str, ...], tuple[str, ...]], list[IncidentEpisode]] = defaultdict(
            list
        )
        for episode in episodes:
            signature = (
                tuple(sorted(item.casefold() for item in episode.service_ids)),
                tuple(sorted(item.casefold() for item in episode.error_codes)),
            )
            if any(signature):
                groups[signature].append(episode)
        created = 0
        for (services, errors), values in groups.items():
            if len(values) < minimum_examples:
                continue
            signature_key = "|".join((*services, *errors))
            existing = await session.scalar(
                select(ProcedureVersion.id).where(
                    ProcedureVersion.compiled_signature == signature_key,
                    ProcedureVersion.status.in_(("candidate", "review", "approved")),
                )
            )
            if existing is not None:
                continue
            action_sets: list[list[EpisodeAction]] = []
            for episode in values:
                actions = list(
                    await session.scalars(
                        select(EpisodeAction)
                        .where(EpisodeAction.episode_id == episode.id)
                        .order_by(EpisodeAction.ordinal)
                    )
                )
                if actions and all(item.name in TOOL_REGISTRY for item in actions):
                    action_sets.append(actions)
            if len(action_sets) < minimum_examples:
                continue
            common = self._common_tool_prefix(action_sets)
            if not common:
                continue
            label = services[0] if services else errors[0]
            key_base = _KEY.sub("_", f"PROC_{label}_RECOVERY".upper()).strip("_")
            key = (key_base[:68] + "_" + hashlib.sha256(signature_key.encode()).hexdigest()[:8])[
                :80
            ]
            definition = ProcedureCandidateDefinition(
                key=key,
                title=f"Verified {label.upper()} recovery workflow",
                intent=f"{label}_recovery",
                description="Workflow compiled from repeated verified support episodes.",
                visibility="company",
                applicability=tuple(
                    [ApplicabilitySignal(signal_type="service", value=item) for item in services]
                    + [ApplicabilitySignal(signal_type="error_code", value=item) for item in errors]
                ),
                steps=tuple(
                    ProcedureStepDefinition(
                        step_key=f"step-{index + 1}",
                        action=f"Execute allowlisted diagnostic action {tool_name}",
                        tool_name=tool_name,
                        expected_observation="Receive a schema-valid tool observation.",
                        on_success=f"step-{index + 2}" if index + 1 < len(common) else None,
                        approval_required=(TOOL_REGISTRY[tool_name].approval_policy == "always"),
                        verification=(
                            "Verify the stated support outcome from a receipt or live readback."
                            if index + 1 == len(common)
                            else None
                        ),
                    )
                    for index, tool_name in enumerate(common)
                ),
                prohibited_actions=("Do not bypass live tool policy or approval.",),
                evidence_refs=tuple(f"incident-episode:{item.id}" for item in values),
                example_episode_ids=tuple(item.id for item in values),
                compiled_signature=signature_key,
            )
            await ProcedureRegistryService().create_candidate(
                session,
                definition=definition,
                created_by=None,
                technician_authored=False,
            )
            created += 1
        return created

    @staticmethod
    def _common_tool_prefix(action_sets: list[list[EpisodeAction]]) -> tuple[str, ...]:
        sequences = [[item.name for item in actions] for actions in action_sets]
        length = min(len(item) for item in sequences)
        common: list[str] = []
        for index in range(length):
            value = sequences[0][index]
            if any(sequence[index] != value for sequence in sequences[1:]):
                break
            common.append(value)
        return tuple(common)
