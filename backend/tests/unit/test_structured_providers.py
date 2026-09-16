import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.providers.fake import FakeTextProvider
from app.providers.openai import OpenAITextProvider
from app.providers.structured import (
    EvidenceInput,
    ProviderContractError,
    SupportReply,
)


def evidence() -> list[EvidenceInput]:
    return [
        EvidenceInput(
            source_id="src_allowed",
            title="VPN setup",
            page_number=2,
            excerpt="Open the VPN client and sign in with SSO.",
        )
    ]


class FakeResponsesApi:
    def __init__(self, reply: SupportReply | None) -> None:
        self.reply = reply
        self.kwargs: dict[str, object] = {}

    async def parse(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return SimpleNamespace(
            id="resp-1",
            output_parsed=self.reply,
            usage=SimpleNamespace(input_tokens=20, output_tokens=8),
        )


def test_support_reply_normalizes_citations_and_enforces_outcome() -> None:
    reply = SupportReply(
        outcome="answered",
        answer="  Follow the guide. ",
        citations=[" src_allowed ", "src_allowed"],
    )
    assert reply.answer == "Follow the guide."
    assert reply.citations == ["src_allowed"]
    with pytest.raises(ValidationError):
        SupportReply(outcome="answered", answer="Unsupported", citations=[])
    with pytest.raises(ValidationError):
        SupportReply(outcome="no_answer", answer="Unknown", citations=["src_allowed"])


def test_fake_provider_obeys_same_structured_contract() -> None:
    async def scenario() -> None:
        provider = FakeTextProvider()
        answered = await provider.generate_support_reply("How?", evidence=evidence())
        assert answered.reply.outcome == "answered"
        assert answered.reply.citations == ["src_allowed"]
        no_answer = await provider.generate_support_reply("Unknown", evidence=[])
        assert no_answer.reply.outcome == "no_answer"
        assert no_answer.reply.citations == []

    asyncio.run(scenario())


def test_openai_adapter_rejects_citation_outside_evidence() -> None:
    async def scenario() -> None:
        api = FakeResponsesApi(
            SupportReply(
                outcome="answered",
                answer="Invented source",
                citations=["src_not_allowed"],
            )
        )
        provider = OpenAITextProvider(client=SimpleNamespace(responses=api), model="gpt-test")
        with pytest.raises(ProviderContractError):
            await provider.generate_support_reply("How?", evidence=evidence())
        assert api.kwargs["store"] is False
        assert api.kwargs["max_output_tokens"] == 400
        assert api.kwargs["text_format"] is SupportReply

    asyncio.run(scenario())


def test_openai_adapter_returns_normalized_usage() -> None:
    async def scenario() -> None:
        api = FakeResponsesApi(
            SupportReply(
                outcome="answered",
                answer="Use SSO.",
                citations=["src_allowed"],
            )
        )
        provider = OpenAITextProvider(client=SimpleNamespace(responses=api), model="gpt-test")
        response = await provider.generate_support_reply("How?", evidence=evidence())
        assert response.provider_request_id == "resp-1"
        assert response.input_tokens == 20
        assert response.output_tokens == 8

    asyncio.run(scenario())
