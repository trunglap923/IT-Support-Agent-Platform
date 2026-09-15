"""Reproducible LangGraph/PostgreSQL pause and cross-process resume probe."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Any, Literal, TypedDict, cast
from uuid import uuid4

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

DATABASE_ENV = "CHECKPOINT_DATABASE_URL"


class ApprovalState(TypedDict, total=False):
    request: str
    approved: bool
    status: str


@dataclass(frozen=True, slots=True)
class PhaseResult:
    phase: Literal["pause", "resume"]
    run_id: str
    process_id: int
    status: str
    approved: bool | None


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    run_id: str
    pause_process_id: int
    resume_process_id: int
    paused_status: str
    resumed_status: str
    approved: bool


def approval_node(state: ApprovalState) -> ApprovalState:
    decision = interrupt(
        {
            "kind": "ticket_approval",
            "request": state["request"],
        }
    )
    if not isinstance(decision, bool):
        raise TypeError("The approval resume value must be a boolean")
    return {
        "approved": decision,
        "status": "approved" if decision else "rejected",
    }


def build_graph(checkpointer: PostgresSaver) -> Any:
    builder = StateGraph(ApprovalState)
    builder.add_node("approval", approval_node)
    builder.add_edge(START, "approval")
    builder.add_edge("approval", END)
    return builder.compile(checkpointer=checkpointer)


def execute_phase(
    *,
    phase: Literal["pause", "resume"],
    database_url: str,
    run_id: str,
) -> PhaseResult:
    config = cast(RunnableConfig, {"configurable": {"thread_id": run_id}})
    with PostgresSaver.from_conn_string(database_url) as checkpointer:
        checkpointer.setup()
        graph = build_graph(checkpointer)
        if phase == "pause":
            output = graph.invoke(
                {"request": "Create a demo IT support ticket", "status": "pending"},
                config=config,
            )
            interrupts = output.get("__interrupt__", ())
            if not interrupts:
                raise RuntimeError("Graph did not pause at the approval interrupt")
            return PhaseResult(
                phase="pause",
                run_id=run_id,
                process_id=os.getpid(),
                status="paused",
                approved=None,
            )

        snapshot = graph.get_state(config)
        if not snapshot.next:
            raise RuntimeError("No paused checkpoint exists for this run_id")
        output = graph.invoke(Command(resume=True), config=config)
        if output.get("status") != "approved" or output.get("approved") is not True:
            raise RuntimeError("Graph did not resume with the expected approval")
        return PhaseResult(
            phase="resume",
            run_id=run_id,
            process_id=os.getpid(),
            status=str(output["status"]),
            approved=bool(output["approved"]),
        )


def _run_child(*, phase: Literal["pause", "resume"], run_id: str, database_url: str) -> PhaseResult:
    environment = os.environ.copy()
    environment[DATABASE_ENV] = database_url
    environment["LANGGRAPH_STRICT_MSGPACK"] = "true"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.agent.checkpoint_spike",
            "--phase",
            phase,
            "--run-id",
            run_id,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return PhaseResult(**json.loads(completed.stdout))


def run_recovery_probe(*, database_url: str, run_id: str | None = None) -> RecoveryResult:
    stable_run_id = run_id or f"checkpoint-spike-{uuid4()}"
    paused = _run_child(phase="pause", run_id=stable_run_id, database_url=database_url)
    resumed = _run_child(phase="resume", run_id=stable_run_id, database_url=database_url)
    if paused.process_id == resumed.process_id:
        raise RuntimeError("Pause and resume unexpectedly ran in the same process")
    if paused.run_id != resumed.run_id:
        raise RuntimeError("Resume used a different run_id")
    return RecoveryResult(
        run_id=stable_run_id,
        pause_process_id=paused.process_id,
        resume_process_id=resumed.process_id,
        paused_status=paused.status,
        resumed_status=resumed.status,
        approved=resumed.approved is True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("pause", "resume"))
    parser.add_argument("--run-id")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database_url = os.getenv(DATABASE_ENV, "").strip()
    if not database_url:
        raise SystemExit(f"Set {DATABASE_ENV} to an isolated PostgreSQL database")

    result: PhaseResult | RecoveryResult
    if args.phase:
        if not args.run_id:
            raise SystemExit("--run-id is required with --phase")
        result = execute_phase(
            phase=args.phase,
            database_url=database_url,
            run_id=args.run_id,
        )
    else:
        result = run_recovery_probe(database_url=database_url, run_id=args.run_id)
    print(json.dumps(asdict(result), ensure_ascii=False))


if __name__ == "__main__":
    main()
