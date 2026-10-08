"""Optional Langfuse tracing with a zero-configuration fake-mode fallback."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager, nullcontext
from threading import Lock
from types import TracebackType
from typing import Any, Protocol, cast

from langfuse import Langfuse, propagate_attributes
from openinference.instrumentation import TraceConfig
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

from app.config import Settings

logger = logging.getLogger(__name__)

_instrumentation_lock = Lock()
_agents_instrumented = False


class GenerationObservation(Protocol):
    @property
    def trace_id(self) -> str | None: ...

    def update(self, **kwargs: Any) -> Any: ...


class AIObserver(Protocol):
    @property
    def capture_content(self) -> bool: ...

    def run(
        self,
        *,
        run_id: str,
        actor_id: str,
        conversation_id: str,
        runtime: str,
        model: str,
        input_text: str,
    ) -> AbstractContextManager[GenerationObservation | None]: ...

    def generation(
        self,
        *,
        run_id: str,
        actor_id: str,
        model: str,
        evidence_count: int,
    ) -> AbstractContextManager[GenerationObservation | None]: ...

    def record_run_usage(
        self,
        *,
        run_id: str,
        model: str,
        model_calls: int,
        input_tokens: int,
        output_tokens: int,
    ) -> None: ...

    def close(self) -> None: ...


class NoopAIObserver:
    @property
    def capture_content(self) -> bool:
        return False

    def run(
        self,
        *,
        run_id: str,
        actor_id: str,
        conversation_id: str,
        runtime: str,
        model: str,
        input_text: str,
    ) -> AbstractContextManager[GenerationObservation | None]:
        del run_id, actor_id, conversation_id, runtime, model, input_text
        return nullcontext(None)

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

    def record_run_usage(
        self,
        *,
        run_id: str,
        model: str,
        model_calls: int,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        del run_id, model, model_calls, input_tokens, output_tokens

    def close(self) -> None:
        return None


class LangfuseAIObserver:
    def __init__(self, client: Langfuse, *, capture_content: bool = False) -> None:
        self._client = client
        self._capture_content = capture_content

    @property
    def capture_content(self) -> bool:
        return self._capture_content

    def run(
        self,
        *,
        run_id: str,
        actor_id: str,
        conversation_id: str,
        runtime: str,
        model: str,
        input_text: str,
    ) -> AbstractContextManager[GenerationObservation | None]:
        actor_hash = _hash_identifier(actor_id)
        conversation_hash = _hash_identifier(conversation_id)

        @contextmanager
        def observe_run() -> Any:
            with (
                self._client.start_as_current_observation(
                    as_type="agent",
                    name="it-support-run",
                    input={"message": input_text} if self._capture_content else None,
                    metadata={
                        "run_id": run_id,
                        "actor_hash": actor_hash,
                        "conversation_hash": conversation_hash,
                        "runtime": runtime,
                        "model": model,
                    },
                ) as observation,
                propagate_attributes(
                    user_id=actor_hash,
                    session_id=conversation_hash,
                    tags=["it-support", runtime],
                    metadata={"run_id": run_id},
                    trace_name="IT Support",
                ),
            ):
                yield observation

        return _SafeObservationContext(observe_run)

    def generation(
        self,
        *,
        run_id: str,
        actor_id: str,
        model: str,
        evidence_count: int,
    ) -> AbstractContextManager[GenerationObservation | None]:
        return _SafeObservationContext(
            lambda: self._client.start_as_current_observation(
                as_type="generation",
                name="support-answer",
                model=model,
                input={"evidence_count": evidence_count},
                metadata={
                    "run_id": run_id,
                    "actor_hash": _hash_identifier(actor_id),
                    "feedback_eligible": True,
                },
            )
        )

    def record_run_usage(
        self,
        *,
        run_id: str,
        model: str,
        model_calls: int,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        total_tokens = input_tokens + output_tokens
        with _SafeObservationContext(
            lambda: self._client.start_as_current_observation(
                as_type="generation",
                name="it-support-run-usage",
                model=model,
                input={"scope": "run_aggregate"},
                output={"model_calls": model_calls},
                usage_details={
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": total_tokens,
                },
                metadata={"run_id": run_id, "aggregate": True},
            )
        ):
            pass

    def close(self) -> None:
        try:
            self._client.flush()
        except Exception:  # Langfuse is an optional telemetry sink.
            logger.warning("Langfuse flush failed; application result is unaffected")


class _SafeObservation:
    def __init__(self, observation: Any) -> None:
        self._observation = observation

    @property
    def trace_id(self) -> str | None:
        try:
            value = self._observation.trace_id
        except Exception:
            logger.warning("Langfuse trace ID lookup failed")
            return None
        return value if isinstance(value, str) else None

    def update(self, **kwargs: Any) -> Any:
        try:
            return self._observation.update(**kwargs)
        except Exception:
            logger.warning("Langfuse observation update failed")
            return None


class _SafeObservationContext(AbstractContextManager[GenerationObservation | None]):
    def __init__(
        self,
        context_factory: Callable[[], AbstractContextManager[Any]],
    ) -> None:
        self._context_factory = context_factory
        self._context: AbstractContextManager[Any] | None = None

    def __enter__(self) -> GenerationObservation | None:
        try:
            self._context = self._context_factory()
            observation = self._context.__enter__()
        except Exception:
            self._context = None
            logger.warning("Langfuse observation start failed; tracing disabled for this scope")
            return None
        return _SafeObservation(observation)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._context is None:
            return None
        if exc_type is not None:
            try:
                sanitized_error = RuntimeError(exc_type.__name__)
                self._context.__exit__(RuntimeError, sanitized_error, None)
            except Exception:
                logger.warning(
                    "Langfuse observation close failed; application result is unaffected"
                )
            return False
        try:
            return cast(bool | None, self._context.__exit__(exc_type, exc_value, traceback))
        except Exception:
            logger.warning("Langfuse observation close failed; application result is unaffected")
            return None


def _hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _instrument_openai_agents(*, capture_content: bool) -> None:
    global _agents_instrumented

    if _agents_instrumented:
        return
    with _instrumentation_lock:
        if _agents_instrumented:
            return
        try:
            OpenAIAgentsInstrumentor().instrument(
                exclusive_processor=True,
                config=TraceConfig(
                    hide_inputs=not capture_content,
                    hide_outputs=not capture_content,
                    hide_llm_invocation_parameters=not capture_content,
                    hide_llm_tools=not capture_content,
                    hide_embeddings_text=True,
                    hide_embeddings_vectors=True,
                    hide_retrieval_documents=not capture_content,
                ),
            )
        except Exception:
            logger.warning("OpenAI Agents instrumentation failed; Langfuse spans are unavailable")
            return
        _agents_instrumented = True


def create_ai_observer(settings: Settings) -> AIObserver:
    public_key = (settings.langfuse_public_key or "").strip()
    secret = settings.langfuse_secret_key
    secret_key = secret.get_secret_value().strip() if secret is not None else ""
    if not public_key or not secret_key:
        return NoopAIObserver()
    _instrument_openai_agents(capture_content=settings.langfuse_capture_content)
    try:
        return LangfuseAIObserver(
            Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                base_url=(settings.langfuse_base_url or "").strip() or None,
                environment=settings.app_env.value,
                release=settings.app_version,
            ),
            capture_content=settings.langfuse_capture_content,
        )
    except Exception:
        logger.warning("Langfuse client initialization failed; using no-op observability")
        return NoopAIObserver()
