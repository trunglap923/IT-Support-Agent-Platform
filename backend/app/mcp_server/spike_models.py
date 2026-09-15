"""Typed actor context shared by the MCP stdio spike client and server."""

from pydantic import BaseModel, ConfigDict


class ActorContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    actor_id: str
    run_id: str


class ActorIdentity(BaseModel):
    actor_id: str
    run_id: str
    sensitive_environment_present: list[str]
