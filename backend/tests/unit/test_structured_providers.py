import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.prompts import SUPPORT_INSTRUCTIONS
from app.providers.fake import FakeTextProvider
from app.providers.openai import OpenAITextProvider
from app.providers.structured import (
    EvidenceInput,
    IncompleteStructuredResponseError,
    InvalidStructuredResponseError,
    ProviderContractError,
    SupportExecutionPlan,
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
    def __init__(self, reply: object | None) -> None:
        self.reply = reply
        self.kwargs: dict[str, object] = {}

    async def parse(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        return SimpleNamespace(
            id="resp-1",
            output_parsed=self.reply,
            usage=SimpleNamespace(input_tokens=20, output_tokens=8),
        )


class FakeResponseStream:
    def __init__(
        self,
        deltas: list[str],
        final_response: object,
        stream_error: Exception | None = None,
    ) -> None:
        self._deltas = deltas
        self._final_response = final_response
        self._stream_error = stream_error

    async def __aiter__(self):  # type: ignore[no-untyped-def]
        for delta in self._deltas:
            yield SimpleNamespace(type="response.output_text.delta", delta=delta)
        if self._stream_error is not None:
            raise self._stream_error

    async def get_final_response(self) -> object:
        return self._final_response


class FakeResponseStreamManager:
    def __init__(self, stream: FakeResponseStream) -> None:
        self._stream = stream

    async def __aenter__(self) -> FakeResponseStream:
        return self._stream

    async def __aexit__(self, *args: object) -> None:
        del args


class FakeStreamingResponsesApi:
    def __init__(
        self,
        reply: SupportReply,
        deltas: list[str],
        stream_error: Exception | None = None,
    ) -> None:
        self.kwargs: dict[str, object] = {}
        response = SimpleNamespace(
            id="resp-stream-1",
            output_parsed=reply,
            usage=SimpleNamespace(input_tokens=22, output_tokens=11),
        )
        self._manager = FakeResponseStreamManager(
            FakeResponseStream(deltas, response, stream_error)
        )

    def stream(self, **kwargs: object) -> FakeResponseStreamManager:
        self.kwargs = kwargs
        return self._manager


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
        deltas: list[str] = []

        async def collect_delta(delta: str) -> None:
            deltas.append(delta)

        streamed = await provider.generate_support_reply(
            "How?",
            evidence=evidence(),
            on_text_delta=collect_delta,
        )
        assert len(deltas) > 1
        assert "".join(deltas) == streamed.reply.answer

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


def test_fake_provider_preserves_edited_ticket_fields() -> None:
    async def scenario() -> None:
        provider = FakeTextProvider()

        response = await provider.choose_support_tool(
            "Tạo ticket hỗ trợ với thông tin sau:\n"
            "Tiêu đề: VPN vẫn lỗi sau khi cấp lại profile\n"
            "Mô tả: Máy Ubuntu vẫn không kết nối được sau khi thử lại.\n"
            "Loại sự cố: vpn\n"
            "Mức độ: high\n"
            "Thiết bị: 11111111-1111-1111-1111-111111111111"
        )

        assert response.call is not None
        assert response.call.arguments == {
            "title": "VPN vẫn lỗi sau khi cấp lại profile",
            "description": "Máy Ubuntu vẫn không kết nối được sau khi thử lại.",
            "issue_type": "vpn",
            "severity": "high",
            "device_id": "11111111-1111-1111-1111-111111111111",
        }

    asyncio.run(scenario())


def test_fake_provider_plans_only_relevant_observable_steps() -> None:
    async def scenario() -> None:
        provider = FakeTextProvider()

        profile = await provider.plan_support_steps(
            "Tôi tên là gì?",
            selected_action="get_my_profile",
        )
        device_issue = await provider.plan_support_steps(
            "VPN lỗi trên máy Ubuntu của tôi",
            selected_action="knowledge",
        )
        greeting = await provider.plan_support_steps(
            "Xin chào",
            selected_action="auto",
        )

        assert profile.plan.steps == ["profile", "answer"]
        assert device_issue.plan.steps == ["device", "knowledge", "answer"]
        assert greeting.plan.action == "direct"
        assert greeting.plan.steps == ["answer"]

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
        assert api.kwargs["max_output_tokens"] == 800
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


def test_openai_adapter_streams_only_decoded_answer_text() -> None:
    async def scenario() -> None:
        expected = 'Use SSO.\nThen say "done".'
        api = FakeStreamingResponsesApi(
            SupportReply(
                outcome="answered",
                answer=expected,
                citations=["src_allowed"],
            ),
            [
                '{"outcome":"answered","ans',
                'wer":"Use ',
                'SSO.\\nThen say \\"done\\".",',
                '"citations":["src_allowed"]}',
            ],
        )
        provider = OpenAITextProvider(client=SimpleNamespace(responses=api), model="gpt-test")
        deltas: list[str] = []

        async def collect_delta(delta: str) -> None:
            deltas.append(delta)

        response = await provider.generate_support_reply(
            "How?",
            evidence=evidence(),
            on_text_delta=collect_delta,
        )

        assert "".join(deltas) == expected
        assert response.reply.answer == expected
        assert response.provider_request_id == "resp-stream-1"
        assert api.kwargs["text_format"] is SupportReply
        assert api.kwargs["store"] is False

    asyncio.run(scenario())


def test_openai_adapter_classifies_truncated_structured_stream() -> None:
    async def scenario() -> None:
        validation_error: ValidationError | None = None
        try:
            SupportReply.model_validate_json('{"outcome":"answered","answer":"cut off')
        except ValidationError as error:
            validation_error = error
        assert validation_error is not None
        api = FakeStreamingResponsesApi(
            SupportReply(
                outcome="answered",
                answer="Unused final response",
                citations=["src_allowed"],
            ),
            ['{"outcome":"answered","answer":"cut off'],
            stream_error=validation_error,
        )
        provider = OpenAITextProvider(client=SimpleNamespace(responses=api), model="gpt-test")

        with pytest.raises(
            IncompleteStructuredResponseError,
            match="stopped before completing",
        ):
            await provider.generate_support_reply(
                "How?",
                evidence=evidence(),
                on_text_delta=async_noop,
            )

    async def async_noop(delta: str) -> None:
        del delta

    asyncio.run(scenario())


def test_openai_adapter_classifies_invalid_structured_stream() -> None:
    async def scenario() -> None:
        validation_error: ValidationError | None = None
        try:
            SupportReply(
                outcome="no_answer",
                answer="The evidence is insufficient.",
                citations=["src_allowed"],
            )
        except ValidationError as error:
            validation_error = error
        assert validation_error is not None
        api = FakeStreamingResponsesApi(
            SupportReply(
                outcome="answered",
                answer="Unused final response",
                citations=["src_allowed"],
            ),
            ['{"outcome":"no_answer","answer":"Insufficient","citations":["src_allowed"]}'],
            stream_error=validation_error,
        )
        provider = OpenAITextProvider(client=SimpleNamespace(responses=api), model="gpt-test")

        with pytest.raises(
            InvalidStructuredResponseError,
            match="A no-answer reply cannot contain citations",
        ):
            await provider.generate_support_reply(
                "How?",
                evidence=evidence(),
                on_text_delta=async_noop,
            )

    async def async_noop(delta: str) -> None:
        del delta

    asyncio.run(scenario())


def test_openai_adapter_includes_server_owned_retry_instruction() -> None:
    async def scenario() -> None:
        api = FakeResponsesApi(
            SupportReply(
                outcome="answered",
                answer="Use SSO.",
                citations=["src_allowed"],
            )
        )
        provider = OpenAITextProvider(client=SimpleNamespace(responses=api), model="gpt-test")

        await provider.generate_support_reply(
            "How?",
            evidence=evidence(),
            retry_instruction="Return a contract-compliant response.",
        )

        assert '"retry_instruction": "Return a contract-compliant response."' in str(
            api.kwargs["input"]
        )

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


def test_openai_adapter_returns_model_generated_execution_plan() -> None:
    async def scenario() -> None:
        api = FakeResponsesApi(
            SupportExecutionPlan(
                action="get_my_profile",
                steps=["profile", "answer"],
            )
        )
        provider = OpenAITextProvider(client=SimpleNamespace(responses=api), model="gpt-test")

        response = await provider.plan_support_steps(
            "Tôi tên là gì?",
            selected_action="get_my_profile",
        )

        assert response.plan.steps == ["profile", "answer"]
        assert api.kwargs["text_format"] is SupportExecutionPlan
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
