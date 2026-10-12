"""Agent-tool adapter around the scoped hybrid knowledge retriever."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.rag.citations.sources import build_evidence_output
from app.rag.retrieval.analysis import evidence_entity_groups, text_covers_entity_groups
from app.rag.retrieval.query import HybridRetriever
from app.tools.schemas import SearchKnowledgeResult


class KnowledgeToolSearch:
    def __init__(
        self,
        *,
        session: AsyncSession,
        principal: Principal,
        retriever: HybridRetriever,
        run_id: str,
        citation_store: dict[str, dict[str, Any]],
        current_query: str,
        minimum_lexical_coverage: float = 0.5,
        minimum_vector_similarity: float = 0.75,
        minimum_evidence_score: float = 0.45,
    ) -> None:
        self._session = session
        self._principal = principal
        self._retriever = retriever
        self._run_id = run_id
        self._citation_store = citation_store
        self._current_query = current_query.strip()
        self._minimum_lexical_coverage = minimum_lexical_coverage
        self._minimum_vector_similarity = minimum_vector_similarity
        self._minimum_evidence_score = minimum_evidence_score
        self._call_index = 0

    async def __call__(self, query: str, limit: int) -> dict[str, object]:
        del query  # Tool arguments cannot replace the latest user request.
        self._call_index += 1
        hits = await self._retriever.search(
            self._session,
            query=self._current_query,
            principal=self._principal,
            operation_id=f"agent:{self._run_id}:knowledge:{self._call_index}",
        )
        analysis = self._retriever.last_analysis
        required_entity_groups = evidence_entity_groups(analysis) if analysis is not None else ()
        output = build_evidence_output(
            hits,
            minimum_lexical_coverage=self._minimum_lexical_coverage,
            minimum_vector_similarity=self._minimum_vector_similarity,
            minimum_evidence_score=self._minimum_evidence_score,
            max_sources=limit,
            required_entity_groups=required_entity_groups,
        )
        hits_by_id = {str(hit.chunk_id): hit for hit in hits}
        sources: list[dict[str, object]] = []
        pending_citations: dict[str, dict[str, Any]] = {}
        for source in output.sources:
            hit = hits_by_id[str(source.chunk_id)]
            score = hit.evidence_score if hit.evidence_score is not None else hit.score
            source_text = " ".join(
                (source.title, source.section or "", *source.section_path, source.excerpt)
            )
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
                "score": score,
                "meets_evidence_threshold": score >= self._minimum_evidence_score,
                "expansion_kind": hit.expansion_kind,
                "matches_query_entities": text_covers_entity_groups(
                    source_text, required_entity_groups
                ),
            }
            pending_citations[source.source_id] = citation
            sources.append(
                {
                    "source_id": source.source_id,
                    "title": source.title,
                    "excerpt": source.excerpt,
                    "page_number": source.page_number,
                }
            )
        payload = {
            "sources": sources,
            "query_analysis": (
                {
                    "intent": analysis.intent,
                    "confidence": analysis.confidence,
                    "service": list(analysis.filters.services),
                    "product": list(analysis.filters.products),
                    "operating_system": list(analysis.filters.operating_systems),
                    "error_codes": list(analysis.filters.error_codes),
                    "versions": list(analysis.filters.version_labels),
                    "version_scope": analysis.filters.version_scope,
                }
                if analysis is not None
                else None
            ),
        }
        # Validate the complete public tool payload before exposing its evidence to
        # later agent turns. ToolExecutor applies this same schema as a second check.
        validated_payload = SearchKnowledgeResult.model_validate(payload).model_dump(mode="json")
        self._citation_store.update(pending_citations)
        return validated_payload
