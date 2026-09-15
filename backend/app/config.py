"""Typed application settings with explicit fake and live provider modes."""

from enum import StrEnum

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AIProvider(StrEnum):
    FAKE = "fake"
    OPENAI = "openai"


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

    ai_provider: AIProvider = AIProvider.FAKE
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1-mini-2025-04-14"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, gt=0)

    database_url: SecretStr | None = None
    migration_database_url: SecretStr | None = None
    redis_url: SecretStr | None = None
    document_storage_path: str = "/data/documents"

    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str | None = None
    log_prompts: bool = False

    app_ai_daily_budget_usd: float = Field(default=1.0, gt=0)
    app_ai_monthly_budget_usd: float = Field(default=10.0, gt=0)

    @model_validator(mode="after")
    def validate_provider_credentials(self) -> "Settings":
        if self.ai_provider is AIProvider.OPENAI:
            key = self.openai_api_key
            if key is None or not key.get_secret_value().strip():
                raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai")
        return self

    def public_summary(self) -> dict[str, str | bool]:
        """Return only values that are safe to expose in diagnostics."""

        return {
            "environment": self.app_env.value,
            "demo_mode": self.demo_mode,
            "ai_provider": self.ai_provider.value,
        }
