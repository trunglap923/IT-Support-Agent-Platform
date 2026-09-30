from __future__ import annotations

import asyncio
from uuid import UUID

from app.agent.rag import RAGGraphNodes
from app.auth.demo_identity import ensure_demo_identity
from app.auth.principal import Principal
from app.db import Database
from app.db.models import Conversation, Message
from app.memory.lifecycle import MemoryLifecycleService
from app.memory.retrieval import MAX_MEMORY_CONTEXT_FACTS, MemoryContextService
from app.providers.fake import FakeTextProvider

PASSWORD = "correct-horse-battery-staple"


def test_memory_context_limit_is_fixed_at_five() -> None:
    assert MAX_MEMORY_CONTEXT_FACTS == 5


def test_confirmed_memory_crosses_conversations_but_device_memory_stays_scoped(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        lifecycle = MemoryLifecycleService()
        try:
            async with database.session() as session, session.begin():
                user = await ensure_demo_identity(session, password=PASSWORD)
                laptop = await lifecycle.create_device(
                    session,
                    owner_id=user.id,
                    label="Laptop công ty",
                    platform="windows",
                )
                phone = await lifecycle.create_device(
                    session,
                    owner_id=user.id,
                    label="Điện thoại",
                    platform="other",
                )
                source_conversation = Conversation(owner_id=user.id, title="Nguồn memory")
                session.add(source_conversation)
                await session.flush()
                source_message = Message(
                    conversation_id=source_conversation.id,
                    role="user",
                    content="Tôi dùng Windows 11. Hãy trả lời bằng tiếng Việt.",
                )
                session.add(source_message)
                await session.flush()
                extraction = await lifecycle.extract_from_message(
                    session,
                    owner_id=user.id,
                    source_message_id=source_message.id,
                )
                assert extraction is not None
                candidates = {value.key: value for value in extraction.candidates}
                await lifecycle.confirm_candidate(
                    session,
                    owner_id=user.id,
                    candidate_id=candidates["operating_system"].id,
                    expected_version=1,
                    device_id=laptop.id,
                )
                await lifecycle.confirm_candidate(
                    session,
                    owner_id=user.id,
                    candidate_id=candidates["preferred_language"].id,
                    expected_version=1,
                    device_id=None,
                )
                laptop_conversation = Conversation(
                    owner_id=user.id, device_id=laptop.id, title="VPN laptop"
                )
                phone_conversation = Conversation(
                    owner_id=user.id, device_id=phone.id, title="VPN phone"
                )
                session.add_all([laptop_conversation, phone_conversation])
                await session.flush()

                laptop_context = await MemoryContextService().context_messages(
                    session, owner_id=user.id, device_id=laptop_conversation.device_id
                )
                phone_context = await MemoryContextService().context_messages(
                    session, owner_id=user.id, device_id=phone_conversation.device_id
                )
                assert {item.content for item in laptop_context} == {
                    "Confirmed user data: operating_system=Windows 11",
                    "Confirmed user data: preferred_language=tiếng Việt",
                }
                assert [item.content for item in phone_context] == [
                    "Confirmed user data: preferred_language=tiếng Việt"
                ]

                principal = Principal(
                    user_id=user.id,
                    session_id=UUID(int=0),
                    email=user.email,
                    display_name=user.display_name,
                    role=user.role,
                    department_id=user.department_id,
                    department_key="engineering",
                )
                nodes = RAGGraphNodes(
                    session=session,
                    principal=principal,
                    retriever=object(),  # type: ignore[arg-type]
                    provider=FakeTextProvider(),
                    history=laptop_context,
                )
                graph_context = await nodes.load_context({"query": "VPN bị lỗi"})
                assert {item["role"] for item in graph_context["history"]} == {"memory"}
                assert len(graph_context["history"]) == 2
        finally:
            await database.close()

    asyncio.run(scenario())
