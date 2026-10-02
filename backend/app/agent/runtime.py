"""Provider-neutral contracts for support-agent runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AgentRuntimeResult:
    answer: str
    outcome: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    approval_proposal: dict[str, Any] | None = None
    serialized_state: str | None = None
    approval_call_id: str | None = None
    model_calls: int = 0
    retrieval_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    provider_request_id: str = ""

    def as_graph_result(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "answer": self.answer,
            "outcome": self.outcome,
            "citations": self.citations,
            "route": "done",
            "model_calls": self.model_calls,
            "retrieval_calls": self.retrieval_calls,
            "tool_calls": self.tool_calls,
            "step_count": self.model_calls + self.tool_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "provider_request_id": self.provider_request_id,
        }
        if self.approval_proposal is not None:
            result["approval_proposal"] = self.approval_proposal
        if self.serialized_state is not None:
            result["serialized_state"] = self.serialized_state
        if self.approval_call_id is not None:
            result["approval_call_id"] = self.approval_call_id
        return result


class AgentRuntime(Protocol):
    async def run(self, *, query: str, serialized_state: str | None = None) -> AgentRuntimeResult:
        """Run or resume one bounded application turn."""

    async def close(self) -> None:
        """Release runtime-owned provider resources."""
