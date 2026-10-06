from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.auth.principal import Principal
from app.db.models import UserRole
from app.rag.retrieval.sparse import (
    Bm25SparseRetriever,
    PostgresSparseRetriever,
    create_sparse_retriever,
)


class FakeResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class FakeSession:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows
        self.execute_calls = 0

    async def execute(self, statement: object) -> FakeResult:
        del statement
        self.execute_calls += 1
        return FakeResult(self._rows)


def _row(identifier: int, *, title: str, content: str) -> object:
    return SimpleNamespace(
        _mapping={
            "chunk_id": UUID(int=identifier),
            "section_id": None,
            "document_id": UUID(int=identifier + 10),
            "version_id": UUID(int=identifier + 20),
            "document_key": f"doc-{identifier}",
            "version_label": "v1",
            "title": title,
            "page_number": None,
            "section": None,
            "content": content,
            "ordinal": 0,
            "section_path": [],
        }
    )


def _principal(*, department_id: int = 100) -> Principal:
    return Principal(
        user_id=UUID(int=90),
        session_id=UUID(int=91),
        email="user@example.com",
        display_name="User",
        role=UserRole.EMPLOYEE,
        department_id=UUID(int=department_id),
        department_key="engineering",
    )


def test_bm25_sparse_retriever_ranks_and_reuses_acl_scoped_index() -> None:
    async def scenario() -> None:
        session = FakeSession(
            [
                _row(
                    1,
                    title="VPN certificate renewal",
                    content="Renew the managed certificate before reconnecting.",
                ),
                _row(
                    2,
                    title="Office printer",
                    content="Replace the paper tray and reconnect the printer.",
                ),
            ]
        )
        retriever = Bm25SparseRetriever()
        now = datetime(2026, 10, 6, tzinfo=UTC)

        first = await retriever.retrieve(  # type: ignore[arg-type]
            session,
            raw_query="managed VPN certificate",
            principal=_principal(),
            now=now,
            limit=2,
        )
        second = await retriever.retrieve(  # type: ignore[arg-type]
            session,
            raw_query="office printer paper",
            principal=_principal(),
            now=datetime(2026, 10, 6, 0, 1, tzinfo=UTC),
            limit=2,
        )

        assert first[0].document_key == "doc-1"
        assert second[0].document_key == "doc-2"
        assert first[0].sparse_rank == 1
        assert first[0].sparse_score is not None
        assert session.execute_calls == 1

        with pytest.raises(RuntimeError, match="ACL scopes"):
            await retriever.retrieve(  # type: ignore[arg-type]
                session,
                raw_query="VPN",
                principal=_principal(department_id=101),
                now=now,
                limit=2,
            )

    asyncio.run(scenario())


def test_sparse_retriever_factory_uses_explicit_strategy() -> None:
    assert isinstance(create_sparse_retriever(strategy="postgres_fts"), PostgresSparseRetriever)
    assert isinstance(create_sparse_retriever(strategy="bm25"), Bm25SparseRetriever)
    with pytest.raises(ValueError, match="Unsupported"):
        create_sparse_retriever(strategy="unknown")
