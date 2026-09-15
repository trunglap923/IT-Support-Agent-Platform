import pytest
from pydantic import ValidationError

from app.config import AIProvider, Settings


def test_fake_provider_is_safe_default() -> None:
    settings = Settings()

    assert settings.ai_provider is AIProvider.FAKE
    assert settings.openai_api_key is None
    assert "openai_api_key" not in settings.public_summary()


def test_openai_mode_requires_key() -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(ai_provider=AIProvider.OPENAI, openai_api_key=None)


def test_openai_mode_accepts_non_empty_key() -> None:
    settings = Settings(
        ai_provider=AIProvider.OPENAI,
        openai_api_key="test-only-placeholder",
    )

    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "test-only-placeholder"


def test_redis_url_is_validated_and_kept_secret() -> None:
    settings = Settings(redis_url="redis://127.0.0.1:6379/0")

    assert settings.redis_url is not None
    assert settings.redis_url.get_secret_value() == "redis://127.0.0.1:6379/0"
    assert "127.0.0.1" not in repr(settings.redis_url)

    with pytest.raises(ValidationError, match="REDIS_URL"):
        Settings(redis_url="http://127.0.0.1:6379")
