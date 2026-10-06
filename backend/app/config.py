"""Typed application settings with explicit fake and live provider modes."""

from enum import StrEnum
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AIProvider(StrEnum):
    FAKE = "fake"
    OPENAI = "openai"


class AgentRuntime(StrEnum):
    AUTO = "auto"
    LANGGRAPH = "langgraph"
    OPENAI_AGENTS = "openai_agents"


class RetrievalReranker(StrEnum):
    WEIGHTED = "weighted"
    CROSS_ENCODER = "cross_encoder"


class Settings(BaseSettings):
    """Configuration read from process environment.

    Loading a local dotenv file is deliberately left to the process launcher so
    configuration does not depend on the current working directory.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "IT Support Agent Platform"
    app_version: str = "0.1.0"
    app_env: AppEnvironment = AppEnvironment.DEVELOPMENT
    demo_mode: bool = True

    text_provider: AIProvider = AIProvider.FAKE
    embedding_provider: AIProvider = AIProvider.FAKE
    agent_runtime: AgentRuntime = AgentRuntime.AUTO
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1-mini-2025-04-14"
    openai_input_price_per_million_usd: float = Field(default=0.40, ge=0)
    openai_output_price_per_million_usd: float = Field(default=1.60, ge=0)
    openai_price_version: str = "2026-09-openai-published"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, gt=0)
    embedding_input_price_per_million_usd: float = Field(default=0.02, ge=0)
    embedding_price_version: str = "2026-09-plan-v1"
    retrieval_branch_limit: int = Field(default=20, ge=5, le=100)
    retrieval_result_limit: int = Field(default=5, ge=1, le=20)
    retrieval_rrf_k: int = Field(default=60, ge=1, le=1000)
    retrieval_max_primary_chunks_per_document: int = Field(default=1, ge=1, le=5)
    retrieval_reranker: RetrievalReranker = RetrievalReranker.WEIGHTED
    retrieval_cross_encoder_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    retrieval_cross_encoder_model_file: str = "onnx/model_quint8_avx2.onnx"
    retrieval_cross_encoder_candidate_limit: int = Field(default=20, ge=1, le=100)
    retrieval_cross_encoder_timeout_seconds: float = Field(default=10.0, gt=0, le=300)

    database_url: SecretStr | None = None
    migration_database_url: SecretStr | None = None
    demo_seed_password: SecretStr | None = None
    redis_url: SecretStr | None = None
    redis_socket_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    readiness_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    celery_agent_concurrency: int = Field(default=2, gt=0, le=8)
    celery_background_concurrency: int = Field(default=1, gt=0, le=4)
    celery_task_soft_time_limit_seconds: int = Field(default=300, gt=0)
    celery_task_time_limit_seconds: int = Field(default=330, gt=0)
    run_lease_seconds: int = Field(default=90, ge=15, le=600)
    run_max_attempts: int = Field(default=3, ge=1, le=10)
    sse_poll_interval_seconds: float = Field(default=0.1, gt=0, le=10)
    sse_heartbeat_seconds: float = Field(default=15.0, gt=0, le=60)
    document_storage_path: str = ".storage/documents"
    demo_corpus_path: str = "../data"
    document_max_pdf_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    document_max_pdf_pages: int = Field(default=100, gt=0, le=1000)
    document_max_extracted_text_bytes: int = Field(default=1024 * 1024, gt=0)

    session_cookie_name: str = "it_support_session"
    csrf_cookie_name: str = "it_support_csrf"
    session_ttl_hours: int = Field(default=8, gt=0, le=24)
    auth_login_rate_limit_enabled: bool = True
    auth_login_max_attempts: int = Field(default=5, gt=0, le=100)
    auth_login_window_seconds: int = Field(default=300, gt=0, le=3600)
    cookie_secure: bool = False
    allowed_web_origin: str = "http://127.0.0.1:5173"

    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str | None = None
    log_prompts: bool = False

    app_ai_daily_budget_usd: float = Field(default=1.0, gt=0)
    app_ai_monthly_budget_usd: float = Field(default=10.0, gt=0)

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return value
        raw_value = value.get_secret_value().strip()
        parsed = urlsplit(raw_value)
        if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
            raise ValueError("REDIS_URL must use redis:// or rediss:// and include a host")
        return SecretStr(raw_value)

    @model_validator(mode="after")
    def validate_provider_credentials(self) -> "Settings":
        if AIProvider.OPENAI in {self.text_provider, self.embedding_provider}:
            key = self.openai_api_key
            if key is None or not key.get_secret_value().strip():
                raise ValueError(
                    "OPENAI_API_KEY is required when TEXT_PROVIDER or EMBEDDING_PROVIDER is openai"
                )
        if self.embedding_dimensions != 1536:
            raise ValueError(
                "EMBEDDING_DIMENSIONS must remain 1536 for the current pgvector schema"
            )
        if (
            self.agent_runtime is AgentRuntime.OPENAI_AGENTS
            and self.text_provider is not AIProvider.OPENAI
        ):
            raise ValueError("AGENT_RUNTIME=openai_agents requires TEXT_PROVIDER=openai")
        if self.app_env is AppEnvironment.PRODUCTION and not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        if self.celery_task_time_limit_seconds <= self.celery_task_soft_time_limit_seconds:
            raise ValueError("CELERY_TASK_TIME_LIMIT_SECONDS must exceed the soft time limit")
        return self

    def public_summary(self) -> dict[str, str | bool]:
        """Return only values that are safe to expose in diagnostics."""

        return {
            "environment": self.app_env.value,
            "demo_mode": self.demo_mode,
            "text_provider": self.text_provider.value,
            "embedding_provider": self.embedding_provider.value,
            "agent_runtime": self.agent_runtime.value,
        }
