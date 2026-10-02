"""Deterministic policy decisions at the tool execution boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.tools.registry import ToolSpec

PolicyAction = Literal["allow", "approval", "deny"]


@dataclass(frozen=True, slots=True)
class ToolPolicyDecision:
    action: PolicyAction
    reason_code: str
    policy_version: str = "tool-policy-v1"


class ToolPolicyEngine:
    def evaluate(self, *, spec: ToolSpec, actor_role: str) -> ToolPolicyDecision:
        if actor_role not in spec.allowed_roles:
            return ToolPolicyDecision(action="deny", reason_code="role_not_allowed")
        if spec.approval_policy == "always":
            return ToolPolicyDecision(action="approval", reason_code="explicit_approval_required")
        return ToolPolicyDecision(action="allow", reason_code="allowlisted_read")
