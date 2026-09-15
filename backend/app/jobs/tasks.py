"""Minimal task contracts; production handlers are added with their feature slices."""

from __future__ import annotations

from typing import TypedDict

from celery import shared_task  # type: ignore[import-untyped]


class FakeTaskReceipt(TypedDict):
    run_id: str
    provider: str
    status: str


@shared_task(name="jobs.run_agent")  # type: ignore[untyped-decorator]
def run_agent(run_id: str) -> FakeTaskReceipt:
    """Deterministic fake-mode task proving the agent queue contract."""

    return {"run_id": run_id, "provider": "fake", "status": "processed"}


@shared_task(name="jobs.reconcile_queued_runs")  # type: ignore[untyped-decorator]
def reconcile_queued_runs() -> dict[str, int]:
    """No-op scheduler seam; database reconciliation arrives in P19."""

    return {"requeued": 0}
