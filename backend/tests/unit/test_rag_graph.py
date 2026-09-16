import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.agent.graph import build_support_graph, run_support_graph
from app.agent.rag import RAGGraphNodes
from app.auth.principal import Principal
from app.db.models import UserRole
from app.providers.fake import FakeTextProvider
from app.rag.retrieval.query import RetrievalHit


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


def hit(*, score: float = 0.04) -> RetrievalHit:
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
        assert result["answer"] == "Open the VPN client and sign in with SSO."
        assert result["citation_ids"] == [result["citations"][0]["source_id"]]
        assert result["citations"][0]["title"] == "VPN guide"
        assert retriever.queries == ["How do I use VPN?"]

    asyncio.run(scenario())


def test_rag_graph_uses_no_answer_without_model_call() -> None:
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
        assert result["model_calls"] == 0

    asyncio.run(scenario())
