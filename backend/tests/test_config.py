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
