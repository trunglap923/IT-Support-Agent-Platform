"""Agent-tool adapter around the scoped hybrid knowledge retriever."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.rag.citations.sources import build_evidence_output
from app.rag.retrieval.query import HybridRetriever


class KnowledgeToolSearch:
    def __init__(
        self,
        *,
        session: AsyncSession,
        principal: Principal,
        retriever: HybridRetriever,
        run_id: str,
        citation_store: dict[str, dict[str, Any]],
        minimum_lexical_coverage: float = 0.5,
        minimum_vector_similarity: float = 0.75,
    ) -> None:
        self._session = session
        self._principal = principal
        self._retriever = retriever
        self._run_id = run_id
        self._citation_store = citation_store
        self._minimum_lexical_coverage = minimum_lexical_coverage
        self._minimum_vector_similarity = minimum_vector_similarity
        self._call_index = 0

    async def __call__(self, query: str, limit: int) -> dict[str, object]:
        self._call_index += 1
        hits = await self._retriever.search(
            self._session,
            query=query,
            principal=self._principal,
            operation_id=f"agent:{self._run_id}:knowledge:{self._call_index}",
        )
        output = build_evidence_output(
            hits[:limit],
            minimum_lexical_coverage=self._minimum_lexical_coverage,
            minimum_vector_similarity=self._minimum_vector_similarity,
        )
        scores = {str(hit.chunk_id): hit.score for hit in hits}
        sources: list[dict[str, object]] = []
        for source in output.sources:
            citation = {
                "source_id": source.source_id,
                "source_url": source.source_url,
                "document_id": str(source.document_id),
                "version_id": str(source.version_id),
                "chunk_id": str(source.chunk_id),
                "document_key": source.document_key,
                "version_label": source.version_label,
                "title": source.title,
                "page_number": source.page_number,
                "section": source.section,
                "excerpt": source.excerpt,
                "score": scores[str(source.chunk_id)],
            }
            self._citation_store[source.source_id] = citation
            sources.append(
                {
                    "source_id": source.source_id,
                    "title": source.title,
                    "excerpt": source.excerpt,
                    "page_number": source.page_number,
                }
            )
        return {"sources": sources}
