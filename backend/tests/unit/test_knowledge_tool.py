import asyncio
from typing import Any
from uuid import UUID

from app.agent.knowledge_tool import KnowledgeToolSearch
from app.auth.principal import Principal
from app.db.models import UserRole


class RecordingRetriever:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.last_analysis = None

    async def search(self, session: object, **kwargs: Any) -> list[Any]:
        del session
        self.queries.append(str(kwargs["query"]))
        return []


def test_knowledge_tool_uses_latest_request_instead_of_model_supplied_old_topic() -> None:
    async def scenario() -> None:
        retriever = RecordingRetriever()
        tool = KnowledgeToolSearch(
            session=None,  # type: ignore[arg-type]
            principal=Principal(
                user_id=UUID(int=1),
                session_id=UUID(int=2),
                email="user@example.com",
                display_name="User",
                role=UserRole.EMPLOYEE,
                department_id=UUID(int=3),
                department_key="engineering",
            ),
            retriever=retriever,  # type: ignore[arg-type]
            run_id="run-1",
            citation_store={},
            current_query="Cách truy cập GitLab?",
        )

        await tool("Khắc phục VPN từ chủ đề cũ", 5)

        assert retriever.queries == ["Cách truy cập GitLab?"]

    asyncio.run(scenario())
