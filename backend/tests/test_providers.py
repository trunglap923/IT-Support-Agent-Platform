import asyncio
from types import SimpleNamespace
from typing import Any

from app.providers.fake import FakeTextProvider
from app.providers.openai import OpenAITextProvider


class StubResponses:
    def __init__(self) -> None:
        self.arguments: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> Any:
        self.arguments = kwargs
        return SimpleNamespace(
            id="resp_test",
            output_text="Nội dung kiểm thử",
            usage=SimpleNamespace(input_tokens=4, output_tokens=3),
        )


class StubOpenAIClient:
    def __init__(self) -> None:
        self.responses = StubResponses()
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def test_fake_provider_is_deterministic() -> None:
    async def run() -> None:
        provider = FakeTextProvider("offline")
        result = await provider.generate_text("ignored")
        assert result.text == "offline"
        assert result.input_tokens == 0

    asyncio.run(run())


def test_openai_adapter_disables_response_storage_without_network() -> None:
    async def run() -> None:
        client = StubOpenAIClient()
        provider = OpenAITextProvider(client=client, model="gpt-4.1-mini-2025-04-14")

        result = await provider.generate_text("hello", max_output_tokens=42)
        await provider.close()

        assert result.provider_request_id == "resp_test"
        assert client.responses.arguments == {
            "model": "gpt-4.1-mini-2025-04-14",
            "input": "hello",
            "max_output_tokens": 42,
            "store": False,
        }
        assert client.closed is True

    asyncio.run(run())
