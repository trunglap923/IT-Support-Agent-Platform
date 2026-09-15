"""Create the configured provider inside the application lifespan."""

from app.config import AIProvider, Settings
from app.providers.base import TextGenerationProvider
from app.providers.fake import FakeTextProvider
from app.providers.openai import build_openai_provider


def create_provider(settings: Settings) -> TextGenerationProvider:
    if settings.ai_provider is AIProvider.FAKE:
        return FakeTextProvider()

    key = settings.openai_api_key
    if key is None:
        raise RuntimeError("OpenAI credentials were not validated")
    return build_openai_provider(
        api_key=key.get_secret_value(),
        model=settings.openai_model,
    )
