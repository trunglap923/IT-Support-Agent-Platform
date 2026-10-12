"""Bounded LangGraph topology for retrieval-backed support answers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agent.state import (
    GRAPH_RECURSION_LIMIT,
    GRAPH_SCHEMA_VERSION,
    MAX_MODEL_CALLS,
    MAX_RETRIEVAL_CALLS,
    SupportAgentState,
)

StateUpdate = dict[str, Any]
AgentNode = Callable[[SupportAgentState], Awaitable[StateUpdate]]


@dataclass(frozen=True, slots=True)
class SupportGraphNodes:
    load_context: AgentNode
    decide_action: AgentNode
    inspect_device: AgentNode
    execute_tool: AgentNode
    respond_tool: AgentNode
    rewrite_query: AgentNode
    retrieve: AgentNode
    decide_evidence: AgentNode
    generate_answer: AgentNode
    validate_answer: AgentNode
    no_answer: AgentNode


def _with_step(node: AgentNode) -> AgentNode:
    async def wrapped(state: SupportAgentState) -> StateUpdate:
        update = await node(state)
        update["step_count"] = state.get("step_count", 0) + 1
        return update

    return wrapped


def _bounded_model(node: AgentNode) -> AgentNode:
    async def wrapped(state: SupportAgentState) -> StateUpdate:
        calls = state.get("model_calls", 0)
        if calls >= MAX_MODEL_CALLS:
            return {
                "model_calls": calls,
                "stop_reason": "model_call_limit",
                "route": "no_answer",
                "step_count": state.get("step_count", 0) + 1,
            }
        update = await node(state)
        consumed_calls = int(update.pop("_model_calls_used", 1))
        update["model_calls"] = calls + max(1, consumed_calls)
        update["step_count"] = state.get("step_count", 0) + 1
        return update

    return wrapped


def _bounded_retrieval(node: AgentNode) -> AgentNode:
    async def wrapped(state: SupportAgentState) -> StateUpdate:
        calls = state.get("retrieval_calls", 0)
        if calls >= MAX_RETRIEVAL_CALLS:
            return {
                "retrieval_calls": calls,
                "evidence": [],
                "stop_reason": "retrieval_call_limit",
                "route": "no_answer",
                "step_count": state.get("step_count", 0) + 1,
            }
        update = await node(state)
        update["retrieval_calls"] = calls + 1
        update["step_count"] = state.get("step_count", 0) + 1
        return update

    return wrapped


def _validated(node: AgentNode) -> AgentNode:
    async def wrapped(state: SupportAgentState) -> StateUpdate:
        if state.get("stop_reason") in {"model_call_limit", "retrieval_call_limit"}:
            return {
                "route": "no_answer",
                "step_count": state.get("step_count", 0) + 1,
            }
        update = await node(state)
        update["step_count"] = state.get("step_count", 0) + 1
        return update

    return wrapped


async def _route_evidence(state: SupportAgentState) -> str:
    return state.get("route", "no_answer")


async def _route_action(state: SupportAgentState) -> str:
    return state.get("action_route", "rag")


async def _route_plan(state: SupportAgentState) -> str:
    tool_call = state.get("tool_call", {})
    # Ticket drafts can be created without a device attached to the conversation.
    # The device inspection node is informational and must not gate that action.
    if (
        "device" in state.get("planned_steps", [])
        and tool_call.get("name") != "create_ticket"
    ):
        return "device"
    return state.get("action_route", "rag")


async def _route_validation(state: SupportAgentState) -> str:
    return state.get("route", "no_answer")


def build_support_graph(nodes: SupportGraphNodes) -> Any:
    builder = StateGraph(SupportAgentState)
    # LangGraph's overloads do not currently accept our generic async node alias,
    # even though it is a supported runtime callable.
    builder.add_node("load_context", cast(Any, _with_step(nodes.load_context)))
    builder.add_node("decide_action", cast(Any, _bounded_model(nodes.decide_action)))
    builder.add_node("inspect_device", cast(Any, _with_step(nodes.inspect_device)))
    builder.add_node("execute_tool", cast(Any, _with_step(nodes.execute_tool)))
    builder.add_node("respond_tool", cast(Any, _with_step(nodes.respond_tool)))
    builder.add_node("rewrite_query", cast(Any, _with_step(nodes.rewrite_query)))
    builder.add_node("retrieve", cast(Any, _bounded_retrieval(nodes.retrieve)))
    builder.add_node("decide_evidence", cast(Any, _with_step(nodes.decide_evidence)))
    builder.add_node("generate_answer", cast(Any, _bounded_model(nodes.generate_answer)))
    builder.add_node("validate_answer", cast(Any, _validated(nodes.validate_answer)))
    builder.add_node("no_answer", cast(Any, _with_step(nodes.no_answer)))
    builder.add_edge(START, "load_context")
    builder.add_edge("load_context", "decide_action")
    builder.add_conditional_edges(
        "decide_action",
        _route_plan,
        {
            "device": "inspect_device",
            "direct": "generate_answer",
            "rag": "rewrite_query",
            "tool": "execute_tool",
        },
    )
    builder.add_conditional_edges(
        "inspect_device",
        _route_action,
        {"direct": "generate_answer", "rag": "rewrite_query", "tool": "execute_tool"},
    )
    builder.add_edge("execute_tool", "respond_tool")
    builder.add_edge("respond_tool", END)
    builder.add_edge("rewrite_query", "retrieve")
    builder.add_edge("retrieve", "decide_evidence")
    builder.add_conditional_edges(
        "decide_evidence",
        _route_evidence,
        {"generate": "generate_answer", "no_answer": "no_answer"},
    )
    builder.add_edge("generate_answer", "validate_answer")
    builder.add_conditional_edges(
        "validate_answer",
        _route_validation,
        {"done": END, "retry": "generate_answer", "no_answer": "no_answer"},
    )
    builder.add_edge("no_answer", END)
    return builder.compile()


async def run_support_graph(
    graph: Any,
    initial_state: SupportAgentState,
) -> SupportAgentState:
    state: SupportAgentState = {
        **initial_state,
        "schema_version": GRAPH_SCHEMA_VERSION,
        "model_calls": 0,
        "retrieval_calls": 0,
        "tool_calls": 0,
        "step_count": 0,
        "validation_errors": [],
    }
    config = cast(RunnableConfig, {"recursion_limit": GRAPH_RECURSION_LIMIT})
    return cast(SupportAgentState, await graph.ainvoke(state, config=config))
