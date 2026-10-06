"""Create the configured provider inside the application lifespan."""

from decimal import Decimal

from openai import AsyncOpenAI

from app.config import AIProvider, Settings
from app.db import Database
from app.providers.base import StructuredResponseProvider
from app.providers.embeddings import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from app.providers.fake import FakeTextProvider
from app.providers.openai import build_openai_provider
from app.services.budget.service import DatabaseUsageLedger


def create_provider(
    settings: Settings, database: Database | None = None
) -> StructuredResponseProvider:
    if settings.text_provider is AIProvider.FAKE:
        return FakeTextProvider()

    key = settings.openai_api_key
    if key is None:
        raise RuntimeError("OpenAI credentials were not validated")
    if database is None:
        raise RuntimeError("Database is required for guarded OpenAI calls")
    ledger = DatabaseUsageLedger(
        database,
        daily_budget_usd=Decimal(str(settings.app_ai_daily_budget_usd)),
        monthly_budget_usd=Decimal(str(settings.app_ai_monthly_budget_usd)),
        input_price_per_million_usd=Decimal(str(settings.openai_input_price_per_million_usd)),
        output_price_per_million_usd=Decimal(str(settings.openai_output_price_per_million_usd)),
        price_version=settings.openai_price_version,
    )
    return build_openai_provider(
        api_key=key.get_secret_value(),
        model=settings.openai_model,
        usage_ledger=ledger,
    )


def create_text_usage_ledger(settings: Settings, database: Database) -> DatabaseUsageLedger:
    return DatabaseUsageLedger(
        database,
        daily_budget_usd=Decimal(str(settings.app_ai_daily_budget_usd)),
        monthly_budget_usd=Decimal(str(settings.app_ai_monthly_budget_usd)),
        input_price_per_million_usd=Decimal(str(settings.openai_input_price_per_million_usd)),
        output_price_per_million_usd=Decimal(str(settings.openai_output_price_per_million_usd)),
        price_version=settings.openai_price_version,
    )


def create_embedding_provider(
    settings: Settings,
    database: Database,
    *,
    timeout_seconds: float = 20.0,
) -> EmbeddingProvider:
    if timeout_seconds <= 0:
        raise ValueError("Embedding provider timeout must be positive")
    if settings.embedding_provider is AIProvider.FAKE:
        return FakeEmbeddingProvider(dimensions=settings.embedding_dimensions)
    key = settings.openai_api_key
    if key is None:
        raise RuntimeError("OpenAI credentials were not validated")
    ledger = DatabaseUsageLedger(
        database,
        daily_budget_usd=Decimal(str(settings.app_ai_daily_budget_usd)),
        monthly_budget_usd=Decimal(str(settings.app_ai_monthly_budget_usd)),
        input_price_per_million_usd=Decimal(str(settings.embedding_input_price_per_million_usd)),
        price_version=settings.embedding_price_version,
    )
    client = AsyncOpenAI(
        api_key=key.get_secret_value(),
        max_retries=0,
        timeout=timeout_seconds,
    )
    return OpenAIEmbeddingProvider(
        client=client,
        ledger=ledger,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
    )
