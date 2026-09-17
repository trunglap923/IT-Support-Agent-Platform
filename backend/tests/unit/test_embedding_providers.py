import asyncio
from types import SimpleNamespace

import pytest

from app.providers.embeddings import FakeEmbeddingProvider, OpenAIEmbeddingProvider
from app.services.budget.service import BudgetExceededError


class RecordingLedger:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def reserve(self, **kwargs: object) -> None:
        self.events.append(f"reserve:{kwargs['operation_id']}")

    async def complete(self, **kwargs: object) -> None:
        self.events.append(f"complete:{kwargs['operation_id']}")

    async def mark_unknown(self, **kwargs: object) -> None:
        self.events.append(f"unknown:{kwargs['operation_id']}")


class FakeEmbeddingsApi:
    def __init__(self, ledger: RecordingLedger, *, fails: bool = False) -> None:
        self._ledger = ledger
        self._fails = fails

    async def create(self, **kwargs: object) -> object:
        assert self._ledger.events == ["reserve:op-1"]
        if self._fails:
            raise TimeoutError("unknown provider outcome")
        dimensions = int(kwargs["dimensions"])
        return SimpleNamespace(
            id="embedding-response-1",
            data=[SimpleNamespace(embedding=[0.25] * dimensions)],
            usage=SimpleNamespace(prompt_tokens=4),
        )


class DenyingLedger(RecordingLedger):
    async def reserve(self, **kwargs: object) -> None:
        del kwargs
        raise BudgetExceededError("test budget exhausted")


class UnexpectedEmbeddingsApi:
    async def create(self, **kwargs: object) -> object:
        del kwargs
        raise AssertionError("provider must not be called after admission is denied")


def test_fake_embeddings_are_deterministic_and_normalized() -> None:
    async def scenario() -> None:
        provider = FakeEmbeddingProvider(dimensions=8)
        first = await provider.embed(["VPN certificate"], operation_id="one")
        second = await provider.embed(["VPN certificate"], operation_id="two")
        assert first.vectors == second.vectors
        assert len(first.vectors[0]) == 8
        assert sum(value * value for value in first.vectors[0]) == pytest.approx(1.0)

    asyncio.run(scenario())


def test_openai_reserves_before_call_and_finalizes_usage() -> None:
    async def scenario() -> None:
        ledger = RecordingLedger()
        client = SimpleNamespace(embeddings=FakeEmbeddingsApi(ledger))
        provider = OpenAIEmbeddingProvider(
            client=client, ledger=ledger, model="text-embedding-3-small", dimensions=4
        )
        result = await provider.embed(["safe test"], operation_id="op-1")
        assert ledger.events == ["reserve:op-1", "complete:op-1"]
        assert result.input_tokens == 4

    asyncio.run(scenario())


def test_unknown_provider_failure_keeps_conservative_reservation() -> None:
    async def scenario() -> None:
        ledger = RecordingLedger()
        client = SimpleNamespace(embeddings=FakeEmbeddingsApi(ledger, fails=True))
        provider = OpenAIEmbeddingProvider(
            client=client, ledger=ledger, model="text-embedding-3-small", dimensions=4
        )
        with pytest.raises(TimeoutError):
            await provider.embed(["safe test"], operation_id="op-1")
        assert ledger.events == ["reserve:op-1", "unknown:op-1"]

    asyncio.run(scenario())


def test_budget_denial_prevents_paid_provider_call() -> None:
    async def scenario() -> None:
        provider = OpenAIEmbeddingProvider(
            client=SimpleNamespace(embeddings=UnexpectedEmbeddingsApi()),
            ledger=DenyingLedger(),
            model="text-embedding-3-small",
            dimensions=4,
        )
        with pytest.raises(BudgetExceededError):
            await provider.embed(["safe test"], operation_id="denied-op")

    asyncio.run(scenario())
