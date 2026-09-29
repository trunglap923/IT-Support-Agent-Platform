import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.prompts import SUPPORT_INSTRUCTIONS
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


class FakeToolResponsesApi:
    def __init__(self, output: list[object]) -> None:
        self.output = output
        self.kwargs: dict[str, object] = {}

    async def create(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return SimpleNamespace(
            id="resp-tool-1",
            output=self.output,
            usage=SimpleNamespace(input_tokens=12, output_tokens=4),
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
        assert answered.reply.answer.startswith("I found relevant internal guidance.")
        assert "1. VPN setup" in answered.reply.answer
        assert answered.reply.citations == ["src_allowed"]
        no_answer = await provider.generate_support_reply("Unknown", evidence=[])
        assert no_answer.reply.outcome == "no_answer"
        assert no_answer.reply.answer.startswith("I couldn't find sufficient")
        assert no_answer.reply.citations == []

    asyncio.run(scenario())


def test_fake_provider_formats_evidence_as_a_deterministic_list() -> None:
    async def scenario() -> None:
        provider = FakeTextProvider()
        evidence_items = [
            EvidenceInput(
                source_id="src_setup",
                title="Setup",
                excerpt="## Authentication\nUse a short-lived token.",
            ),
            EvidenceInput(
                source_id="src_escalation",
                title="Escalation",
                excerpt="## Escalation data\nInclude the request ID.",
            ),
        ]

        answered = await provider.generate_support_reply("How?", evidence=evidence_items)

        assert answered.reply.answer == (
            "I found relevant internal guidance. Follow the documented steps below:\n\n"
            "1. Setup\n   Authentication Use a short-lived token.\n\n"
            "2. Escalation\n   Escalation data Include the request ID."
        )

    asyncio.run(scenario())


def test_fake_provider_groups_duplicate_documents_and_omits_title_chunks() -> None:
    async def scenario() -> None:
        provider = FakeTextProvider()
        evidence_items = [
            EvidenceInput(
                source_id="src_title",
                title="Thiết lập VPN demo",
                excerpt="# Thiết lập VPN demo",
            ),
            EvidenceInput(
                source_id="src_steps",
                title="Thiết lập VPN demo",
                excerpt="## Ubuntu\nCài client, nhập URL công ty demo và đăng nhập SSO.",
            ),
            EvidenceInput(
                source_id="src_steps_duplicate",
                title="Thiết lập VPN demo",
                excerpt="## Ubuntu\nCài client, nhập URL công ty demo và đăng nhập SSO.",
            ),
        ]

        answered = await provider.generate_support_reply(
            "Cách cấu hình VPN trên Ubuntu?",
            evidence=evidence_items,
        )

        assert answered.reply.answer.count("Thiết lập VPN demo") == 1
        assert answered.reply.answer.count("Cài client") == 1
        assert answered.reply.citations == ["src_steps"]

    asyncio.run(scenario())


def test_fake_provider_localizes_vietnamese_summary_and_no_answer() -> None:
    async def scenario() -> None:
        provider = FakeTextProvider()

        answered = await provider.generate_support_reply(
            "Tôi cấu hình VPN như thế nào?",
            evidence=evidence(),
        )
        no_answer = await provider.generate_support_reply(
            "Giúp tôi kiểm tra chủ đề này",
            evidence=[],
        )

        assert answered.reply.answer.startswith("Tôi đã tìm thấy hướng dẫn nội bộ")
        assert "1. VPN setup" in answered.reply.answer
        assert no_answer.reply.answer.startswith("Tôi chưa tìm thấy tài liệu nội bộ")

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
        assert api.kwargs["instructions"] == SUPPORT_INSTRUCTIONS

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


def test_openai_adapter_preserves_allowlisted_tool_call_id() -> None:
    async def scenario() -> None:
        api = FakeToolResponsesApi(
            [
                SimpleNamespace(
                    type="function_call",
                    call_id="call-provider-123",
                    name="check_service_status",
                    arguments='{"service_id":"vpn"}',
                )
            ]
        )
        provider = OpenAITextProvider(client=SimpleNamespace(responses=api), model="gpt-test")
        response = await provider.choose_support_tool("VPN có đang lỗi không?")
        assert response.call is not None
        assert response.call.call_id == "call-provider-123"
        assert response.call.arguments == {"service_id": "vpn"}
        assert api.kwargs["parallel_tool_calls"] is False
        assert api.kwargs["max_tool_calls"] == 1
        assert api.kwargs["store"] is False

    asyncio.run(scenario())


def test_openai_adapter_rejects_unallowlisted_tool_call() -> None:
    async def scenario() -> None:
        api = FakeToolResponsesApi(
            [
                SimpleNamespace(
                    type="function_call",
                    call_id="call-bad",
                    name="search_knowledge_base",
                    arguments="{}",
                )
            ]
        )
        provider = OpenAITextProvider(client=SimpleNamespace(responses=api), model="gpt-test")
        with pytest.raises(ProviderContractError):
            await provider.choose_support_tool("Search knowledge")

    asyncio.run(scenario())
