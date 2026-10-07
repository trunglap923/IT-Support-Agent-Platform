import asyncio
from collections.abc import Sequence
from dataclasses import replace
from uuid import UUID

from app.rag.retrieval.models import QuerySpec, RetrievalCandidate, RetrievalRequest
from app.rag.retrieval.rerank import (
    CrossEncoderReranker,
    FusionScoreReranker,
    WeightedFeatureReranker,
    create_reranker,
)


def _candidate(index: int, content: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=UUID(int=index),
        document_id=UUID(int=100 + index),
        version_id=UUID(int=200 + index),
        document_key=f"document-{index}",
        version_label="v1",
        title=f"Title {index}",
        content=content,
        fusion_score=1 / index,
    )


def test_cross_encoder_reranks_only_the_bounded_candidate_pool() -> None:
    class Scorer:
        def __init__(self) -> None:
            self.pairs: Sequence[tuple[str, str]] = ()

        async def score(self, pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
            self.pairs = pairs
            return [0.1, 0.9]

    async def scenario() -> None:
        scorer = Scorer()
        reranker = CrossEncoderReranker(
            scorer=scorer,
            model="test-model",
            max_candidates=2,
            timeout_seconds=1,
        )
        candidates = [
            _candidate(1, "first"),
            _candidate(2, "second"),
            _candidate(3, "remainder"),
        ]

        ranked = await reranker.rerank("vpn", candidates)

        assert [item.chunk_id for item in ranked] == [UUID(int=2), UUID(int=1), UUID(int=3)]
        assert len(scorer.pairs) == 2
        assert scorer.pairs[0][0] == "vpn"
        assert "first" in scorer.pairs[0][1]
        assert reranker.attempt_count == 1
        assert reranker.fallback_count == 0

    asyncio.run(scenario())


def test_cross_encoder_timeout_falls_back_to_weighted_ranking() -> None:
    class SlowScorer:
        async def score(self, pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
            await asyncio.sleep(0.05)
            return [1.0 for _ in pairs]

    async def scenario() -> None:
        reranker = CrossEncoderReranker(
            scorer=SlowScorer(),
            model="slow-model",
            timeout_seconds=0.001,
        )
        candidates = [
            _candidate(1, "unrelated content"),
            _candidate(2, "vpn setup instructions"),
        ]

        ranked = await reranker.rerank("vpn setup", candidates)

        assert ranked[0].chunk_id == UUID(int=2)
        assert reranker.attempt_count == 1
        assert reranker.fallback_count == 1

    asyncio.run(scenario())


def test_cross_encoder_invalid_score_count_falls_back() -> None:
    class InvalidScorer:
        async def score(self, pairs: Sequence[tuple[str, str]]) -> Sequence[float]:
            return []

    async def scenario() -> None:
        reranker = CrossEncoderReranker(
            scorer=InvalidScorer(),
            model="invalid-model",
            timeout_seconds=1,
        )

        ranked = await reranker.rerank("vpn", [_candidate(1, "vpn")])

        assert len(ranked) == 1
        assert reranker.fallback_count == 1

    asyncio.run(scenario())


def test_weighted_reranker_soft_boosts_matching_metadata() -> None:
    async def scenario() -> None:
        analysis = QuerySpec.from_request(
            RetrievalRequest(raw_query="Cấu hình Registry"),
            intent="knowledge",
            confidence=0.9,
            metadata_filters=(("service", "registry"),),
        )
        matching = _candidate(1, "setup steps")
        matching = replace(matching, document_key="registry-guide")
        unrelated = _candidate(2, "setup steps")

        ranked = await WeightedFeatureReranker().rerank(
            "Cấu hình Registry",
            [unrelated, matching],
            analysis=analysis,
        )

        assert ranked[0].chunk_id == matching.chunk_id
        assert ranked[0].metadata_score == 1.0
        assert ranked[1].metadata_score == 0.0

    asyncio.run(scenario())


def test_fusion_score_reranker_preserves_calibrated_order() -> None:
    async def scenario() -> None:
        candidates = [_candidate(1, "first"), _candidate(2, "second")]

        ranked = await FusionScoreReranker().rerank("ignored", candidates)

        assert [item.chunk_id for item in ranked] == [UUID(int=1), UUID(int=2)]
        assert [item.rerank_score for item in ranked] == [1.0, 0.5]

    asyncio.run(scenario())


def test_reranker_factory_supports_fusion_score_strategy() -> None:
    reranker = create_reranker(
        strategy="fusion",
        model="unused",
        model_file="unused",
        max_candidates=20,
        timeout_seconds=10,
    )

    assert isinstance(reranker, FusionScoreReranker)


def test_fusion_score_reranker_normalizes_small_rrf_scores() -> None:
    async def scenario() -> None:
        candidates = [
            replace(_candidate(1, "first"), fusion_score=0.02),
            replace(_candidate(2, "second"), fusion_score=0.01),
        ]

        ranked = await FusionScoreReranker().rerank("ignored", candidates)

        assert [item.rerank_score for item in ranked] == [1.0, 0.5]

    asyncio.run(scenario())
