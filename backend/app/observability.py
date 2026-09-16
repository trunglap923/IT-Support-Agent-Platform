"""Optional Langfuse tracing with a zero-configuration fake-mode fallback."""

from __future__ import annotations

import hashlib
from contextlib import AbstractContextManager, nullcontext
from typing import Any, Protocol

from langfuse import Langfuse

from app.config import Settings


class GenerationObservation(Protocol):
    @property
    def trace_id(self) -> str | None: ...

    def update(self, **kwargs: Any) -> Any: ...


class AIObserver(Protocol):
    def generation(
        self,
        *,
        run_id: str,
        actor_id: str,
        model: str,
        evidence_count: int,
    ) -> AbstractContextManager[GenerationObservation | None]: ...

    def close(self) -> None: ...


class NoopAIObserver:
    def generation(
        self,
        *,
        run_id: str,
        actor_id: str,
        model: str,
        evidence_count: int,
    ) -> AbstractContextManager[GenerationObservation | None]:
        del run_id, actor_id, model, evidence_count
        return nullcontext(None)

    def close(self) -> None:
        return None


class LangfuseAIObserver:
    def __init__(self, client: Langfuse) -> None:
        self._client = client

    def generation(
        self,
        *,
        run_id: str,
        actor_id: str,
        model: str,
        evidence_count: int,
    ) -> AbstractContextManager[GenerationObservation | None]:
        actor_hash = hashlib.sha256(actor_id.encode()).hexdigest()[:16]
        return self._client.start_as_current_observation(
            as_type="generation",
            name="support-answer",
            model=model,
            input={"evidence_count": evidence_count},
            metadata={
                "run_id": run_id,
                "actor_hash": actor_hash,
                "feedback_eligible": True,
            },
        )

    def close(self) -> None:
        self._client.flush()


def create_ai_observer(settings: Settings) -> AIObserver:
    public_key = (settings.langfuse_public_key or "").strip()
    secret = settings.langfuse_secret_key
    if not public_key or secret is None or not secret.get_secret_value().strip():
        return NoopAIObserver()
    return LangfuseAIObserver(
        Langfuse(
            public_key=public_key,
            secret_key=secret.get_secret_value(),
            base_url=settings.langfuse_base_url,
            environment=settings.app_env.value,
            release=settings.app_version,
        )
    )
