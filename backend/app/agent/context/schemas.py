"""Typed context selected for a single support-agent run."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.agent.context.builder import ContextMessage
from app.auth.principal import Principal


@dataclass(frozen=True, slots=True)
class DeviceContext:
    id: UUID
    label: str
    platform: str


@dataclass(frozen=True, slots=True)
class SupportContext:
    principal: Principal
    conversation_id: UUID
    query: str
    history: tuple[ContextMessage, ...]
    memories: tuple[ContextMessage, ...]
    device: DeviceContext | None

    @property
    def model_history(self) -> list[ContextMessage]:
        return [*self.history, *self.memories]
