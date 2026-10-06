"""Bounded rerankers for a hybrid retrieval candidate pool."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import replace
from functools import lru_cache
from importlib import import_module
from typing import Any, Protocol

from app.diagnostics import log_event
from app.rag.retrieval.analysis import meaningful_terms
from app.rag.retrieval.models import RetrievalCandidate

logger = logging.getLogger(__name__)


class Reranker(Protocol):
    @property
    def name(self) -> str: ...

    async def rerank(
        self, query: str, candidates: list[RetrievalCandidate]
    ) -> list[RetrievalCandidate]: ...


class CrossEncoderScorer(Protocol):
    """Small adapter contract that keeps the optional ML dependency isolated."""

    async def score(self, pairs: Sequence[tuple[str, str]]) -> Sequence[float]: ...


class WeightedFeatureReranker:
    """Rerank using query-term coverage, exact identifier overlap, and RRF.

    This remains the cheap production default and the fallback for an unavailable
    or slow cross encoder.
    """

    @property
    def name(self) -> str:
        return "weighted_feature_v1"

    async def rerank(
        self, query: str, candidates: list[RetrievalCandidate]
    ) -> list[RetrievalCandidate]:
        query_terms = tuple(dict.fromkeys(meaningful_terms(query)))
        exact_terms = tuple(
            term.casefold()
            for term in query.split()
            if any(char.isdigit() for char in term) or any(char in "._-/\\" for char in term)
        )
        max_rrf = max((item.fusion_score for item in candidates), default=0.0) or 1.0
        ranked: list[RetrievalCandidate] = []
        for candidate in candidates:
            searchable = _candidate_text(candidate).casefold()
            content_terms = set(meaningful_terms(searchable, limit=1_000))
            coverage = (
                len(set(query_terms) & content_terms) / len(query_terms) if query_terms else 0.0
            )
            identifier_match = (
                sum(term in searchable for term in exact_terms) / len(exact_terms)
                if exact_terms
                else 0.0
            )
            normalized_rrf = candidate.fusion_score / max_rrf
            dense = candidate.dense_score or 0.0
            score = 0.55 * coverage + 0.25 * identifier_match + 0.15 * normalized_rrf + 0.05 * dense
            ranked.append(replace(candidate, rerank_score=score))
        return _sort_candidates(ranked)


class OnnxCrossEncoderScorer:
    """Lazy CPU adapter for a Hugging Face cross encoder exported to ONNX."""

    def __init__(self, *, model: str, model_file: str) -> None:
        self.model = model
        self.model_file = model_file

    async def score(self, pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
        return await asyncio.to_thread(self._score_sync, pairs)

    def _score_sync(self, pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
        numpy = import_module("numpy")
        tokenizer, session = _load_onnx_model(self.model, self.model_file)
        encodings = tokenizer.encode_batch(list(pairs))
        values_by_name = {
            "input_ids": [encoding.ids for encoding in encodings],
            "attention_mask": [encoding.attention_mask for encoding in encodings],
            "token_type_ids": [encoding.type_ids for encoding in encodings],
        }
        inputs = {
            item.name: numpy.asarray(values_by_name[item.name], dtype=numpy.int64)
            for item in session.get_inputs()
            if item.name in values_by_name
        }
        logits = session.run(None, inputs)[0]
        return [float(value) for value in numpy.asarray(logits).reshape(-1)]


@lru_cache(maxsize=4)
def _load_onnx_model(model_name: str, model_file: str) -> tuple[Any, Any]:
    try:
        hub = import_module("huggingface_hub")
        onnxruntime = import_module("onnxruntime")
        tokenizers = import_module("tokenizers")
    except ImportError as error:
        raise RuntimeError(
            "Cross-encoder reranking requires the 'cross-encoder' dependency extra"
        ) from error
    tokenizer_path = hub.hf_hub_download(repo_id=model_name, filename="tokenizer.json")
    model_path = hub.hf_hub_download(repo_id=model_name, filename=model_file)
    tokenizer = tokenizers.Tokenizer.from_file(tokenizer_path)
    tokenizer.enable_truncation(max_length=512)
    tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
    session = onnxruntime.InferenceSession(
        model_path,
        providers=["CPUExecutionProvider"],
    )
    return tokenizer, session


class CrossEncoderReranker:
    """Score bounded query/chunk pairs and fall back on deterministic ranking."""

    def __init__(
        self,
        *,
        scorer: CrossEncoderScorer,
        model: str,
        max_candidates: int = 20,
        timeout_seconds: float = 10.0,
        fallback: Reranker | None = None,
    ) -> None:
        if max_candidates < 1:
            raise ValueError("Cross-encoder candidate limit must be positive")
        if timeout_seconds <= 0:
            raise ValueError("Cross-encoder timeout must be positive")
        self._scorer = scorer
        self._model = model
        self._max_candidates = max_candidates
        self._timeout_seconds = timeout_seconds
        self._fallback = fallback or WeightedFeatureReranker()
        self.attempt_count = 0
        self.fallback_count = 0
        self.total_duration_ms = 0.0
        self.durations_ms: list[float] = []

    @property
    def name(self) -> str:
        return f"cross_encoder:{self._model}"

    async def rerank(
        self, query: str, candidates: list[RetrievalCandidate]
    ) -> list[RetrievalCandidate]:
        if not candidates:
            return []
        bounded = candidates[: self._max_candidates]
        remainder = candidates[self._max_candidates :]
        pairs = [(query, _candidate_text(candidate)) for candidate in bounded]
        started_at = time.monotonic()
        self.attempt_count += 1
        try:
            scores = await asyncio.wait_for(
                self._scorer.score(pairs),
                timeout=self._timeout_seconds,
            )
            if len(scores) != len(bounded):
                raise ValueError("Cross encoder returned an unexpected number of scores")
            reranked = [
                replace(candidate, rerank_score=float(score))
                for candidate, score in zip(bounded, scores, strict=True)
            ]
            ranked_remainder = await self._fallback.rerank(query, remainder)
            return [*_sort_candidates(reranked), *ranked_remainder]
        except Exception as error:
            self.fallback_count += 1
            log_event(
                logger,
                "retrieval.reranker.fallback",
                reranker=self.name,
                error_type=type(error).__name__,
                candidate_count=len(bounded),
            )
            return await self._fallback.rerank(query, candidates)
        finally:
            duration_ms = (time.monotonic() - started_at) * 1_000
            self.total_duration_ms += duration_ms
            self.durations_ms.append(duration_ms)


def create_reranker(
    *,
    strategy: str,
    model: str,
    model_file: str,
    max_candidates: int,
    timeout_seconds: float,
) -> Reranker:
    """Construct the configured reranker without importing optional ML packages."""

    if strategy == "weighted":
        return WeightedFeatureReranker()
    if strategy == "cross_encoder":
        return CrossEncoderReranker(
            scorer=OnnxCrossEncoderScorer(model=model, model_file=model_file),
            model=f"{model}/{model_file}",
            max_candidates=max_candidates,
            timeout_seconds=timeout_seconds,
        )
    raise ValueError(f"Unsupported retrieval reranker: {strategy}")


def _candidate_text(candidate: RetrievalCandidate) -> str:
    return "\n".join(
        part
        for part in (
            candidate.title,
            candidate.section or "",
            " > ".join(candidate.section_path),
            candidate.content,
        )
        if part
    )


def _sort_candidates(candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
    return sorted(
        candidates,
        key=lambda item: (
            -(item.rerank_score or 0.0),
            -item.fusion_score,
            item.document_key,
            item.ordinal,
        ),
    )
