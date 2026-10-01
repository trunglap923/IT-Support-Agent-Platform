import asyncio
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from app.agent.graph import build_support_graph, run_support_graph
from app.agent.rag import RAGGraphNodes
from app.auth.principal import Principal
from app.db.models import UserRole
from app.providers.fake import FakeTextProvider
from app.providers.structured import (
    IncompleteStructuredResponseError,
    InvalidStructuredResponseError,
)
from app.rag.retrieval.query import RetrievalHit
from app.tools.results import ToolResult


def principal() -> Principal:
    return Principal(
        user_id=uuid4(),
        session_id=uuid4(),
        email="employee@example.com",
        display_name="Employee",
        role=UserRole.EMPLOYEE,
        department_id=uuid4(),
        department_key="engineering",
    )


class StubRetriever:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits
        self.queries: list[str] = []

    async def search(self, session: object, **kwargs: object) -> list[RetrievalHit]:
        del session
        self.queries.append(str(kwargs["query"]))
        return self.hits


class TruncatedOnceProvider(FakeTextProvider):
    def __init__(self) -> None:
        super().__init__()
        self.output_token_limits: list[int] = []
        self.operation_ids: list[str] = []

    async def generate_support_reply(self, query: str, **kwargs: Any):  # type: ignore[no-untyped-def]
        self.output_token_limits.append(int(kwargs["max_output_tokens"]))
        self.operation_ids.append(str(kwargs["operation_id"]))
        if len(self.output_token_limits) == 1:
            callback = kwargs.get("on_text_delta")
            if callback is not None:
                await callback("partial answer")
            raise IncompleteStructuredResponseError("truncated")
        return await super().generate_support_reply(query, **kwargs)


class InvalidStructuredProvider(FakeTextProvider):
    def __init__(self, *, fail_once: bool) -> None:
        super().__init__()
        self.fail_once = fail_once
        self.calls = 0
        self.operation_ids: list[str] = []
        self.retry_instructions: list[str | None] = []

    async def generate_support_reply(self, query: str, **kwargs: Any):  # type: ignore[no-untyped-def]
        self.calls += 1
        self.operation_ids.append(str(kwargs["operation_id"]))
        self.retry_instructions.append(kwargs.get("retry_instruction"))
        if not self.fail_once or self.calls == 1:
            callback = kwargs.get("on_text_delta")
            if callback is not None:
                await callback("invalid partial answer")
            raise InvalidStructuredResponseError("outcome and citations disagree")
        return await super().generate_support_reply(query, **kwargs)


class StubToolRunner:
    def __init__(self, result: ToolResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs: object) -> ToolResult:
        self.calls.append(kwargs)
        return self.result


def hit(
    *,
    score: float = 0.8,
    vector_similarity: float | None = 0.8,
    lexical_coverage: float = 0.5,
) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        version_id=uuid4(),
        document_key="vpn-guide",
        version_label="v1",
        title="VPN guide",
        page_number=2,
        section="Sign in",
        content="Open the VPN client and sign in with SSO.",
        score=score,
        vector_rank=1,
        lexical_rank=1,
        vector_similarity=vector_similarity,
        lexical_coverage=lexical_coverage,
    )


def test_rag_graph_returns_server_owned_citation() -> None:
    async def scenario() -> None:
        retriever = StubRetriever([hit()])
        nodes = RAGGraphNodes(
            session=SimpleNamespace(),  # type: ignore[arg-type]
            principal=principal(),
            retriever=retriever,  # type: ignore[arg-type]
            provider=FakeTextProvider(),
        )
        result = await run_support_graph(
            build_support_graph(nodes.graph_nodes()),
            {"query": "  How do I use VPN?  ", "run_id": "run-1"},
        )
        assert result["outcome"] == "answered"
        assert result["answer"] == (
            "I found relevant internal guidance. Follow the documented steps below:\n\n"
            "1. VPN guide\n   Open the VPN client and sign in with SSO."
        )
        assert result["citation_ids"] == [result["citations"][0]["source_id"]]
        assert result["citations"][0]["title"] == "VPN guide"
        assert retriever.queries == ["How do I use VPN?"]

    asyncio.run(scenario())


def test_rag_graph_retries_incomplete_output_and_resets_stream() -> None:
    async def scenario() -> None:
        provider = TruncatedOnceProvider()
        stream_starts = 0
        streamed_answer = ""

        async def start_stream() -> None:
            nonlocal stream_starts, streamed_answer
            stream_starts += 1
            streamed_answer = ""

        async def collect_delta(delta: str) -> None:
            nonlocal streamed_answer
            streamed_answer += delta

        nodes = RAGGraphNodes(
            session=SimpleNamespace(),  # type: ignore[arg-type]
            principal=principal(),
            retriever=StubRetriever([hit()]),  # type: ignore[arg-type]
            provider=provider,
            on_stream_started=start_stream,
            on_text_delta=collect_delta,
        )
        result = await run_support_graph(
            build_support_graph(nodes.graph_nodes()),
            {"query": "How do I use VPN?", "run_id": "run-retry"},
        )

        assert provider.output_token_limits == [800, 1_200]
        assert provider.operation_ids[1].endswith(":incomplete-retry")
        assert stream_starts == 2
        assert "partial answer" not in streamed_answer
        assert streamed_answer == result["answer"]
        assert result["outcome"] == "answered"

    asyncio.run(scenario())


def test_rag_graph_retries_invalid_output_with_contract_instruction() -> None:
    async def scenario() -> None:
        provider = InvalidStructuredProvider(fail_once=True)
        stream_starts = 0
        streamed_answer = ""

        async def start_stream() -> None:
            nonlocal stream_starts, streamed_answer
            stream_starts += 1
            streamed_answer = ""

        async def collect_delta(delta: str) -> None:
            nonlocal streamed_answer
            streamed_answer += delta

        nodes = RAGGraphNodes(
            session=SimpleNamespace(),  # type: ignore[arg-type]
            principal=principal(),
            retriever=StubRetriever([hit()]),  # type: ignore[arg-type]
            provider=provider,
            on_stream_started=start_stream,
            on_text_delta=collect_delta,
        )
        result = await run_support_graph(
            build_support_graph(nodes.graph_nodes()),
            {"query": "How do I use VPN?", "run_id": "run-contract-retry"},
        )

        assert provider.calls == 2
        assert provider.operation_ids[1].endswith(":contract-retry")
        assert provider.retry_instructions[0] is None
        assert "outcome='no_answer' only with citations=[]" in str(provider.retry_instructions[1])
        assert stream_starts == 2
        assert "invalid partial answer" not in streamed_answer
        assert streamed_answer == result["answer"]
        assert result["outcome"] == "answered"

    asyncio.run(scenario())


def test_rag_graph_falls_back_safely_after_repeated_invalid_output() -> None:
    async def scenario() -> None:
        provider = InvalidStructuredProvider(fail_once=False)
        stream_starts = 0
        streamed_answer = ""

        async def start_stream() -> None:
            nonlocal stream_starts, streamed_answer
            stream_starts += 1
            streamed_answer = ""

        async def collect_delta(delta: str) -> None:
            nonlocal streamed_answer
            streamed_answer += delta

        nodes = RAGGraphNodes(
            session=SimpleNamespace(),  # type: ignore[arg-type]
            principal=principal(),
            retriever=StubRetriever([hit()]),  # type: ignore[arg-type]
            provider=provider,
            on_stream_started=start_stream,
            on_text_delta=collect_delta,
        )
        result = await run_support_graph(
            build_support_graph(nodes.graph_nodes()),
            {"query": "How do I use VPN?", "run_id": "run-contract-fallback"},
        )

        assert provider.calls == 2
        assert stream_starts == 3
        assert streamed_answer == ""
        assert result["outcome"] == "no_answer"
        assert result["citations"] == []
        assert "Vui lòng liên hệ IT" in result["answer"]

    asyncio.run(scenario())


def test_rag_graph_generates_natural_no_answer_without_evidence() -> None:
    async def scenario() -> None:
        nodes = RAGGraphNodes(
            session=SimpleNamespace(),  # type: ignore[arg-type]
            principal=principal(),
            retriever=StubRetriever([]),  # type: ignore[arg-type]
            provider=FakeTextProvider(),
        )
        result = await run_support_graph(
            build_support_graph(nodes.graph_nodes()),
            {"query": "Unknown internal topic", "run_id": "run-2"},
        )
        assert result["outcome"] == "no_answer"
        assert result["citations"] == []
        assert result["answer"].startswith("I couldn't find sufficient internal documentation")
        assert result["model_calls"] == 2

    asyncio.run(scenario())


def test_rag_graph_uses_no_answer_for_weak_evidence() -> None:
    async def scenario() -> None:
        nodes = RAGGraphNodes(
            session=SimpleNamespace(),  # type: ignore[arg-type]
            principal=principal(),
            retriever=StubRetriever([hit(score=0.7, vector_similarity=0.7, lexical_coverage=0.25)]),  # type: ignore[arg-type]
            provider=FakeTextProvider(),
        )
        result = await run_support_graph(
            build_support_graph(nodes.graph_nodes()),
            {"query": "Unrelated question", "run_id": "run-3"},
        )
        assert result["outcome"] == "no_answer"
        assert result["citations"] == []
        assert result["answer"].startswith("I couldn't find sufficient internal documentation")
        assert result["model_calls"] == 2

    asyncio.run(scenario())


def test_graph_routes_profile_question_without_retrieval() -> None:
    async def scenario() -> None:
        runner = StubToolRunner(
            ToolResult(
                call_id="call-profile",
                name="get_my_profile",
                status="success",
                data={"display_name": "Lập"},
            )
        )
        progress: list[tuple[str, str]] = []

        async def on_progress(
            stage: str,
            status: str,
            detail: str | None,
            count: int | None,
        ) -> None:
            del detail, count
            progress.append((stage, status))

        retriever = StubRetriever([])
        nodes = RAGGraphNodes(
            session=SimpleNamespace(),  # type: ignore[arg-type]
            principal=principal(),
            retriever=retriever,  # type: ignore[arg-type]
            provider=FakeTextProvider(),
            tool_runner=runner,
            on_progress=on_progress,
        )
        result = await run_support_graph(
            build_support_graph(nodes.graph_nodes()),
            {"query": "Tôi tên là gì?", "run_id": "run-profile"},
        )

        assert result["outcome"] == "answered"
        assert "Lập" in result["answer"]
        assert result["retrieval_calls"] == 0
        assert runner.calls[0]["name"] == "get_my_profile"
        assert ("profile", "pending") in progress
        assert ("profile", "completed") in progress
        assert not any(stage in {"device", "knowledge"} for stage, _ in progress)

    asyncio.run(scenario())


def test_graph_routes_service_status_tool_from_model_decision() -> None:
    async def scenario() -> None:
        retriever = StubRetriever([])
        runner = StubToolRunner(
            ToolResult(
                call_id="call-1",
                name="check_service_status",
                status="success",
                data={
                    "service_id": "vpn",
                    "status": "degraded",
                    "message": "VPN is degraded.",
                },
            )
        )
        nodes = RAGGraphNodes(
            session=SimpleNamespace(),  # type: ignore[arg-type]
            principal=principal(),
            retriever=retriever,  # type: ignore[arg-type]
            provider=FakeTextProvider(),
            tool_runner=runner,
        )
        result = await run_support_graph(
            build_support_graph(nodes.graph_nodes()),
            {"query": "Trạng thái VPN hiện tại thế nào?", "run_id": "run-tool-1"},
        )
        assert result["outcome"] == "answered"
        assert "degraded" in result["answer"]
        assert result["tool_calls"] == 1
        assert result["retrieval_calls"] == 0
        assert runner.calls[0]["name"] == "check_service_status"

    asyncio.run(scenario())


def test_graph_routes_owned_ticket_read_without_retrieval() -> None:
    async def scenario() -> None:
        runner = StubToolRunner(
            ToolResult(
                call_id="call-2",
                name="get_my_open_tickets",
                status="success",
                data={
                    "tickets": [
                        {
                            "display_key": "IT-1001",
                            "title": "VPN access",
                            "status": "open",
                        }
                    ]
                },
            )
        )
        nodes = RAGGraphNodes(
            session=SimpleNamespace(),  # type: ignore[arg-type]
            principal=principal(),
            retriever=StubRetriever([]),  # type: ignore[arg-type]
            provider=FakeTextProvider(),
            tool_runner=runner,
        )
        result = await run_support_graph(
            build_support_graph(nodes.graph_nodes()),
            {"query": "Cho tôi xem ticket đang mở của tôi", "run_id": "run-tool-2"},
        )
        assert result["outcome"] == "answered"
        assert "IT-1001" in result["answer"]
        assert runner.calls[0]["arguments"] == {}

    asyncio.run(scenario())


def test_graph_routes_recent_ticket_history_including_resolved() -> None:
    async def scenario() -> None:
        runner = StubToolRunner(
            ToolResult(
                call_id="call-recent",
                name="get_my_recent_tickets",
                status="success",
                data={
                    "tickets": [
                        {
                            "display_key": "IT-0999",
                            "title": "Registry token",
                            "status": "resolved",
                        }
                    ]
                },
            )
        )
        nodes = RAGGraphNodes(
            session=SimpleNamespace(),  # type: ignore[arg-type]
            principal=principal(),
            retriever=StubRetriever([]),  # type: ignore[arg-type]
            provider=FakeTextProvider(),
            tool_runner=runner,
        )
        result = await run_support_graph(
            build_support_graph(nodes.graph_nodes()),
            {"query": "Cho tôi xem ticket gần đây", "run_id": "run-tool-recent"},
        )
        assert result["outcome"] == "answered"
        assert "IT-0999" in result["answer"]
        assert "gần đây" in result["answer"]
        assert runner.calls[0]["name"] == "get_my_recent_tickets"

    asyncio.run(scenario())


def test_graph_returns_ticket_proposal_without_executing_write() -> None:
    async def scenario() -> None:
        runner = StubToolRunner(
            ToolResult(
                call_id="call-ticket",
                name="create_ticket",
                status="failed",
                error={"code": "approval_required", "retryable": False},
            )
        )
        nodes = RAGGraphNodes(
            session=SimpleNamespace(),  # type: ignore[arg-type]
            principal=principal(),
            retriever=StubRetriever([]),  # type: ignore[arg-type]
            provider=FakeTextProvider(),
            tool_runner=runner,
        )
        result = await run_support_graph(
            build_support_graph(nodes.graph_nodes()),
            {
                "query": "Tạo ticket giúp tôi vì VPN không kết nối được.",
                "run_id": "run-tool-ticket",
            },
        )
        assert result["outcome"] == "approval_required"
        assert result["approval_proposal"]["issue_type"] == "vpn"
        assert result["tool_calls"] == 1
        assert "xác nhận" in result["answer"]

    asyncio.run(scenario())
