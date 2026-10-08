"""Bounded hybrid ranking shared by semantic, episodic and procedural memory."""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.providers.embeddings import EmbeddingProvider

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[\w.-]+", re.UNICODE)
_EMBEDDING_DIMENSIONS = 1536


def memory_terms(value: str) -> tuple[str, ...]:
    return tuple(item.casefold() for item in _TOKEN.findall(value) if len(item) > 1)


def recency_score(
    timestamp: datetime | None,
    *,
    now: datetime | None = None,
    half_life_days: float = 180.0,
) -> float:
    if timestamp is None:
        return 0.5
    current = now or datetime.now(UTC)
    normalized = timestamp if timestamp.tzinfo is not None else timestamp.replace(tzinfo=UTC)
    age_days = max(0.0, (current - normalized).total_seconds() / 86_400)
    return math.exp(-math.log(2) * age_days / half_life_days)


@dataclass(frozen=True, slots=True)
class HybridMemoryQuery:
    text: str
    terms: tuple[str, ...]
    vector: tuple[float, ...] | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None

    @classmethod
    def lexical(cls, text: str) -> HybridMemoryQuery:
        return cls(text=text, terms=memory_terms(text))


@dataclass(frozen=True, slots=True)
class HybridMemoryItem:
    item_id: str
    text: str
    embedding: tuple[float, ...] | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    exact_terms: tuple[str, ...] = ()
    recency: float = 0.5
    confidence: float = 0.5
    authority: float = 0.5


@dataclass(frozen=True, slots=True)
class HybridMemoryScore:
    item_id: str
    score: float
    relevance: float
    bm25: float
    vector_similarity: float
    exact_match: float
    recency: float
    confidence: float
    authority: float


@dataclass(frozen=True, slots=True)
class GeneratedMemoryEmbedding:
    vector: tuple[float, ...]
    model: str
    dimensions: int


async def generate_memory_embedding(
    provider: EmbeddingProvider | None,
    text: str,
    *,
    operation_id: str,
) -> GeneratedMemoryEmbedding | None:
    """Attempt one memory embedding without making the durable write unavailable."""

    if provider is None:
        return None
    try:
        batch = await provider.embed([text], operation_id=operation_id)
        if batch.dimensions != _EMBEDDING_DIMENSIONS or len(batch.vectors) != 1:
            raise ValueError("Memory embedding response has an unexpected shape")
        return GeneratedMemoryEmbedding(
            vector=batch.vectors[0],
            model=batch.model,
            dimensions=batch.dimensions,
        )
    except Exception as error:
        logger.warning(
            "memory.embedding.failed operation_id=%s error_type=%s",
            operation_id,
            type(error).__name__,
        )
        return None


class HybridMemoryRetriever:
    """Rank a small ACL-filtered candidate pool with lexical, vector and metadata signals."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        *,
        k1: float = 0.9,
        b: float = 0.4,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._k1 = k1
        self._b = b

    async def prepare_query(self, query: str, *, operation_id: str) -> HybridMemoryQuery:
        embedding = await generate_memory_embedding(
            self._embedding_provider, query, operation_id=operation_id
        )
        return HybridMemoryQuery(
            text=query,
            terms=memory_terms(query),
            vector=embedding.vector if embedding is not None else None,
            embedding_model=embedding.model if embedding is not None else None,
            embedding_dimensions=embedding.dimensions if embedding is not None else None,
        )

    def rank(
        self,
        query: HybridMemoryQuery,
        items: Sequence[HybridMemoryItem],
        *,
        limit: int,
    ) -> tuple[HybridMemoryScore, ...]:
        if limit < 1 or not items:
            return ()
        bm25_scores = self._bm25(query, items)
        maximum_bm25 = max(bm25_scores.values(), default=0.0)
        normalized_query = f" {' '.join(query.text.casefold().split())} "
        values: list[HybridMemoryScore] = []
        for item in items:
            bm25 = bm25_scores[item.item_id] / maximum_bm25 if maximum_bm25 > 0 else 0.0
            embeddings_compatible = (
                query.embedding_model is not None
                and query.embedding_model == item.embedding_model
                and query.embedding_dimensions is not None
                and query.embedding_dimensions == item.embedding_dimensions
            )
            vector_similarity = self._cosine(
                query.vector if embeddings_compatible else None,
                item.embedding if embeddings_compatible else None,
            )
            exact_match = self._exact_score(normalized_query, item.exact_terms)
            retrieval_weights = 0.45 + 0.15
            retrieval_total = 0.45 * bm25 + 0.15 * exact_match
            if embeddings_compatible and query.vector is not None and item.embedding is not None:
                retrieval_weights += 0.40
                retrieval_total += 0.40 * vector_similarity
            relevance = retrieval_total / retrieval_weights
            if relevance <= 0:
                continue
            score = (
                0.78 * relevance
                + 0.08 * _bounded(item.recency)
                + 0.08 * _bounded(item.confidence)
                + 0.06 * _bounded(item.authority)
            )
            values.append(
                HybridMemoryScore(
                    item_id=item.item_id,
                    score=score,
                    relevance=relevance,
                    bm25=bm25,
                    vector_similarity=vector_similarity,
                    exact_match=exact_match,
                    recency=_bounded(item.recency),
                    confidence=_bounded(item.confidence),
                    authority=_bounded(item.authority),
                )
            )
        values.sort(key=lambda item: (-item.score, item.item_id))
        return tuple(values[:limit])

    def _bm25(
        self,
        query: HybridMemoryQuery,
        items: Sequence[HybridMemoryItem],
    ) -> dict[str, float]:
        documents = {item.item_id: memory_terms(item.text) for item in items}
        document_frequencies: Counter[str] = Counter()
        for tokens in documents.values():
            document_frequencies.update(set(tokens))
        document_count = len(documents)
        average_length = sum(map(len, documents.values())) / max(1, document_count)
        query_terms = set(query.terms)
        scores: dict[str, float] = {}
        for item_id, tokens in documents.items():
            frequencies = Counter(tokens)
            length_normalization = 1 - self._b + self._b * len(tokens) / max(1.0, average_length)
            score = 0.0
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if frequency == 0:
                    continue
                document_frequency = document_frequencies[term]
                inverse_document_frequency = math.log(
                    1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                score += inverse_document_frequency * (
                    frequency * (self._k1 + 1) / (frequency + self._k1 * length_normalization)
                )
            scores[item_id] = score
        return scores

    @staticmethod
    def _cosine(left: tuple[float, ...] | None, right: tuple[float, ...] | None) -> float:
        if left is None or right is None or len(left) != len(right):
            return 0.0
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return _bounded(
            sum(a * b for a, b in zip(left, right, strict=True)) / left_norm / right_norm
        )

    @staticmethod
    def _exact_score(normalized_query: str, exact_terms: Sequence[str]) -> float:
        normalized = tuple(
            f" {' '.join(item.casefold().split())} " for item in exact_terms if item.strip()
        )
        if not normalized:
            return 0.0
        matches = sum(item in normalized_query for item in normalized)
        return min(1.0, matches / min(3, len(normalized)))


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, value))
