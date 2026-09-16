import asyncio
from typing import Any

from app.agent.context.builder import ContextMessage, build_agent_context
from app.agent.graph import SupportGraphNodes, build_support_graph, run_support_graph
from app.agent.state import MAX_MODEL_CALLS, SupportAgentState


class FakeNodes:
    def __init__(self, *, validation_failures: int = 0, has_evidence: bool = True) -> None:
        self.validation_failures = validation_failures
        self.has_evidence = has_evidence
        self.generated = 0

    async def load_context(self, state: SupportAgentState) -> dict[str, Any]:
        return {"context_estimated_tokens": len(state["query"].split())}

    async def rewrite_query(self, state: SupportAgentState) -> dict[str, Any]:
        return {"normalized_query": state["query"].strip().casefold()}

    async def retrieve(self, state: SupportAgentState) -> dict[str, Any]:
        del state
        return {
            "evidence": (
                [
                    {
                        "source_id": "src_1",
                        "document_id": "document-1",
                        "version_id": "version-1",
                        "chunk_id": "chunk-1",
                        "document_key": "vpn-setup",
                        "version_label": "v1",
                        "title": "VPN setup",
                        "page_number": 1,
                        "section": "Ubuntu",
                        "excerpt": "Use SSO.",
                        "score": 0.04,
                    }
                ]
                if self.has_evidence
                else []
            )
        }

    async def decide_evidence(self, state: SupportAgentState) -> dict[str, Any]:
        return {"route": "generate" if state.get("evidence") else "no_answer"}

    async def generate_answer(self, state: SupportAgentState) -> dict[str, Any]:
        del state
        self.generated += 1
        return {"answer": "Use SSO.", "citation_ids": ["src_1"]}

    async def validate_answer(self, state: SupportAgentState) -> dict[str, Any]:
        del state
        if self.generated <= self.validation_failures:
            return {"route": "retry", "validation_errors": ["invalid citation"]}
        return {"route": "done", "outcome": "answered", "validation_errors": []}

    async def no_answer(self, state: SupportAgentState) -> dict[str, Any]:
        del state
        return {
            "answer": "Không tìm thấy tài liệu đủ căn cứ.",
            "citation_ids": [],
            "outcome": "no_answer",
            "route": "done",
        }

    def graph_nodes(self) -> SupportGraphNodes:
        return SupportGraphNodes(
            load_context=self.load_context,
            rewrite_query=self.rewrite_query,
            retrieve=self.retrieve,
            decide_evidence=self.decide_evidence,
            generate_answer=self.generate_answer,
            validate_answer=self.validate_answer,
            no_answer=self.no_answer,
        )


def test_graph_generates_answer_with_bounded_retry() -> None:
    async def scenario() -> None:
        fake = FakeNodes(validation_failures=1)
        result = await run_support_graph(
            build_support_graph(fake.graph_nodes()),
            {"query": "  VPN Ubuntu  "},
        )
        assert result["outcome"] == "answered"
        assert result["citation_ids"] == ["src_1"]
        assert result["model_calls"] == 3
        assert result["retrieval_calls"] == 1
        assert result["step_count"] < 24

    asyncio.run(scenario())


def test_graph_stops_after_model_call_budget() -> None:
    async def scenario() -> None:
        fake = FakeNodes(validation_failures=MAX_MODEL_CALLS + 2)
        result = await run_support_graph(
            build_support_graph(fake.graph_nodes()),
            {"query": "VPN Ubuntu"},
        )
        assert result["outcome"] == "no_answer"
        assert result["stop_reason"] == "model_call_limit"
        assert result["model_calls"] == MAX_MODEL_CALLS

    asyncio.run(scenario())


def test_context_preserves_query_and_drops_old_history_first() -> None:
    context = build_agent_context(
        current_query="current VPN question",
        history=[
            ContextMessage(role="user", content="old " * 20),
            ContextMessage(role="assistant", content="recent answer"),
        ],
        max_input_tokens=12,
    )
    assert context.current_query == "current VPN question"
    assert [message.content for message in context.history] == ["recent answer"]
    assert context.truncated is True
