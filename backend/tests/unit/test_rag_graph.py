import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.agent.graph import build_support_graph, run_support_graph
from app.agent.rag import RAGGraphNodes
from app.auth.principal import Principal
from app.db.models import UserRole
from app.providers.fake import FakeTextProvider
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


def test_rag_graph_uses_no_answer_without_answer_generation() -> None:
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
        assert result["model_calls"] == 1

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
        assert result["model_calls"] == 1

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
