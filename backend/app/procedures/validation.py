"""Deterministic safety validation before a procedure can be published."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.models import ProcedureStep
from app.tools.registry import TOOL_REGISTRY

PROCEDURE_VALIDATION_POLICY = "procedure-validation-v1"


@dataclass(frozen=True, slots=True)
class ProcedureValidationReport:
    passed: bool
    policy_version: str
    checks: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "policy_version": self.policy_version,
            "checks": list(self.checks),
        }


class ProcedureSandboxValidator:
    """Replay the workflow graph against registry and approval invariants."""

    def validate(self, steps: list[ProcedureStep]) -> ProcedureValidationReport:
        checks: list[str] = []
        if not steps or len(steps) > 40:
            return ProcedureValidationReport(False, PROCEDURE_VALIDATION_POLICY, ("step_count",))
        keys = {step.step_key for step in steps}
        if len(keys) != len(steps):
            return ProcedureValidationReport(False, PROCEDURE_VALIDATION_POLICY, ("unique_steps",))
        checks.append("bounded_unique_steps")
        graph: dict[str, tuple[str, ...]] = {}
        for step in steps:
            targets = tuple(item for item in (step.on_success, step.on_failure) if item)
            if not set(targets).issubset(keys):
                return ProcedureValidationReport(
                    False, PROCEDURE_VALIDATION_POLICY, ("valid_transitions",)
                )
            graph[step.step_key] = targets
            if step.tool_name is None:
                if step.approval_required:
                    return ProcedureValidationReport(
                        False, PROCEDURE_VALIDATION_POLICY, ("manual_approval_claim",)
                    )
                continue
            spec = TOOL_REGISTRY.get(step.tool_name)
            if spec is None:
                return ProcedureValidationReport(
                    False, PROCEDURE_VALIDATION_POLICY, ("allowlisted_tools",)
                )
            if step.approval_required != (spec.approval_policy == "always"):
                return ProcedureValidationReport(
                    False, PROCEDURE_VALIDATION_POLICY, ("live_approval_policy",)
                )
        checks.extend(("valid_transitions", "allowlisted_tools", "live_approval_policy"))
        if self._has_cycle(graph):
            return ProcedureValidationReport(False, PROCEDURE_VALIDATION_POLICY, ("acyclic",))
        checks.append("acyclic")
        if not any(step.verification for step in steps):
            return ProcedureValidationReport(
                False, PROCEDURE_VALIDATION_POLICY, ("postcondition_verification",)
            )
        checks.append("postcondition_verification")
        return ProcedureValidationReport(True, PROCEDURE_VALIDATION_POLICY, tuple(checks))

    @staticmethod
    def _has_cycle(graph: dict[str, tuple[str, ...]]) -> bool:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            if any(visit(target) for target in graph[node]):
                return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)
