"""Persistent LangGraph interrupt used for ticket approval."""

from __future__ import annotations

import os
from typing import Any, TypedDict, cast
from uuid import UUID

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy.engine import make_url


class TicketApprovalState(TypedDict, total=False):
    run_id: str
    actor_id: str
    approval_id: str
    arguments_hash: str
    approved: bool
    status: str


class ApprovalCheckpointError(RuntimeError):
    pass


def _approval_node(state: TicketApprovalState) -> TicketApprovalState:
    decision = interrupt(
        {
            "kind": "ticket_approval",
            "approval_id": state["approval_id"],
            "arguments_hash": state["arguments_hash"],
        }
    )
    if not isinstance(decision, bool):
        raise ApprovalCheckpointError("Approval decision must be boolean")
    return {
        "approved": decision,
        "status": "approved" if decision else "rejected",
    }


def _build_graph(checkpointer: PostgresSaver) -> Any:
    builder = StateGraph(TicketApprovalState)
    builder.add_node("approval", _approval_node)
    builder.add_edge(START, "approval")
    builder.add_edge("approval", END)
    return builder.compile(checkpointer=checkpointer)


def checkpoint_database_url(async_database_url: str) -> str:
    url = make_url(async_database_url)
    if url.drivername != "postgresql+asyncpg":
        raise ApprovalCheckpointError("Checkpoint source must use postgresql+asyncpg")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def pause_ticket_approval(
    *,
    database_url: str,
    checkpoint_thread_id: str,
    run_id: UUID,
    actor_id: UUID,
    approval_id: UUID,
    arguments_hash: str,
) -> None:
    config = cast(RunnableConfig, {"configurable": {"thread_id": checkpoint_thread_id}})
    with PostgresSaver.from_conn_string(checkpoint_database_url(database_url)) as checkpointer:
        output = _build_graph(checkpointer).invoke(
            {
                "run_id": str(run_id),
                "actor_id": str(actor_id),
                "approval_id": str(approval_id),
                "arguments_hash": arguments_hash,
                "status": "pending",
            },
            config=config,
        )
    if not output.get("__interrupt__"):
        raise ApprovalCheckpointError("Approval graph did not pause")


def resume_ticket_approval(
    *,
    database_url: str,
    checkpoint_thread_id: str,
    run_id: UUID,
    actor_id: UUID,
    approval_id: UUID,
    arguments_hash: str,
    approved: bool,
) -> TicketApprovalState:
    config = cast(RunnableConfig, {"configurable": {"thread_id": checkpoint_thread_id}})
    with PostgresSaver.from_conn_string(checkpoint_database_url(database_url)) as checkpointer:
        graph = _build_graph(checkpointer)
        snapshot = graph.get_state(config)
        values = cast(dict[str, object], snapshot.values)
        expected = {
            "run_id": str(run_id),
            "actor_id": str(actor_id),
            "approval_id": str(approval_id),
            "arguments_hash": arguments_hash,
        }
        if any(values.get(key) != value for key, value in expected.items()):
            raise ApprovalCheckpointError("Checkpoint does not match the approved action")
        if snapshot.next:
            result = cast(
                TicketApprovalState,
                graph.invoke(Command(resume=approved), config=config),
            )
        else:
            # A worker can crash after LangGraph persisted the resume but before the
            # application transaction finalized the run. Treat the matching terminal
            # checkpoint as a durable receipt so a reclaimed lease can finish safely.
            result = cast(TicketApprovalState, values)
    if result.get("approved") is not approved:
        raise ApprovalCheckpointError("Checkpoint resumed with an unexpected decision")
    return result
