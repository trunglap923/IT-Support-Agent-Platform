"""Deterministic fake and budget-guarded OpenAI embedding providers."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.budget.service import DatabaseUsageLedger


@dataclass(frozen=True, slots=True)
class EmbeddingBatch:
    vectors: tuple[tuple[float, ...], ...]
    model: str
    dimensions: int
    provider_request_id: str
    input_tokens: int


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str], *, operation_id: str) -> EmbeddingBatch:
        """Embed a non-empty batch using a unique operation ID."""

    async def close(self) -> None: ...


def estimate_input_tokens(texts: list[str]) -> int:
    return max(1, sum(math.ceil(len(text.encode("utf-8")) / 3) for text in texts))


def validate_embedding_input(texts: list[str]) -> None:
    if not texts or any(not text.strip() for text in texts):
        raise ValueError("Embedding input must contain non-empty strings")
    estimates = [estimate_input_tokens([text]) for text in texts]
    if any(tokens > 8192 for tokens in estimates):
        raise ValueError("An embedding input exceeds the 8192-token safety limit")
    if sum(estimates) > 300_000:
        raise ValueError("Embedding batch exceeds the 300000-token safety limit")


class FakeEmbeddingProvider:
    def __init__(self, *, dimensions: int = 1536, model: str = "fake-embedding-v2") -> None:
        if dimensions <= 0:
            raise ValueError("Embedding dimensions must be positive")
        self._dimensions = dimensions
        self._model = model

    async def embed(self, texts: list[str], *, operation_id: str) -> EmbeddingBatch:
        validate_embedding_input(texts)
        vectors: list[tuple[float, ...]] = []
        for text in texts:
            values = [0.0] * self._dimensions
            for token in re.findall(r"\w+", text.casefold()):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                index = int.from_bytes(digest[:4], "big") % self._dimensions
                sign = 1.0 if digest[4] & 1 else -1.0
                values[index] += sign
            norm = math.sqrt(sum(value * value for value in values)) or 1.0
            vectors.append(tuple(value / norm for value in values))
        return EmbeddingBatch(
            vectors=tuple(vectors),
            model=self._model,
            dimensions=self._dimensions,
            provider_request_id=f"fake-{operation_id}",
            input_tokens=0,
        )

    async def close(self) -> None:
        return None


class OpenAIEmbeddingProvider:
    def __init__(
        self,
        *,
        client: Any,
        ledger: DatabaseUsageLedger,
        model: str,
        dimensions: int,
    ) -> None:
        self._client = client
        self._ledger = ledger
        self._model = model
        self._dimensions = dimensions

    async def embed(self, texts: list[str], *, operation_id: str) -> EmbeddingBatch:
        validate_embedding_input(texts)
        estimated_tokens = estimate_input_tokens(texts)
        client_request_id = f"emb-{hashlib.sha256(operation_id.encode('utf-8')).hexdigest()}"
        await self._ledger.reserve(
            operation_id=operation_id,
            provider="openai",
            model=self._model,
            estimated_input_tokens=estimated_tokens,
        )
        try:
            response = await self._client.embeddings.create(
                input=texts,
                model=self._model,
                dimensions=self._dimensions,
                encoding_format="float",
                extra_headers={"X-Client-Request-Id": client_request_id},
            )
            vectors = tuple(
                tuple(float(value) for value in item.embedding) for item in response.data
            )
            if len(vectors) != len(texts) or any(
                len(vector) != self._dimensions for vector in vectors
            ):
                raise RuntimeError("Embedding response shape does not match the request")
            input_tokens = int(response.usage.prompt_tokens)
            provider_request_id = response._request_id or client_request_id
            await self._ledger.complete(
                operation_id=operation_id,
                actual_input_tokens=input_tokens,
                provider_request_id=provider_request_id,
            )
        except Exception:
            await self._ledger.mark_unknown(operation_id=operation_id)
            raise
        return EmbeddingBatch(
            vectors=vectors,
            model=self._model,
            dimensions=self._dimensions,
            provider_request_id=provider_request_id,
            input_tokens=input_tokens,
        )

    async def close(self) -> None:
        await self._client.close()
