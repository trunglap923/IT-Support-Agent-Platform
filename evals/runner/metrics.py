"""Local load/latency and token-cost measurements for evaluation artifacts."""

from __future__ import annotations

import asyncio
import math
import statistics
import time
from decimal import Decimal
from typing import Any

from app.providers.fake import FakeTextProvider

from evals.runner.harness import execute_case
from evals.runner.load_cases import load_cases, select_cases


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


async def measure_local_fake_load(
    *, concurrency: int = 3, batches: int = 10, seed: int = 20260916
) -> dict[str, Any]:
    selected = select_cases(
        load_cases("development"), category="rag", max_cases=concurrency, seed=seed
    )
    provider = FakeTextProvider()
    latencies: list[float] = []
    failures = 0
    started = time.perf_counter()
    try:
        for batch in range(batches):
            results = await asyncio.gather(
                *[
                    execute_case(
                        case,
                        repetition=batch + 1,
                        provider=provider,
                        run_id=f"load-{seed}",
                        max_output_tokens=160,
                    )
                    for case in selected
                ]
            )
            latencies.extend(result.latency_ms for result in results)
            failures += sum(
                not bool(result.scores["deterministic_pass"]) for result in results
            )
    finally:
        await provider.close()
    elapsed = time.perf_counter() - started
    return {
        "workload": "in-process LangGraph RAG with deterministic fake provider",
        "concurrency": concurrency,
        "batches": batches,
        "request_count": len(latencies),
        "failures": failures,
        "p50_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(_percentile(latencies, 0.95), 3),
        "max_ms": round(max(latencies), 3),
        "wall_seconds": round(elapsed, 3),
        "approval_wait_included": False,
        "qualifies_for_g09": False,
    }


def calculate_report_cost(
    report: dict[str, Any], *, input_price: Decimal, output_price: Decimal
) -> dict[str, Any]:
    totals = report["token_totals"]
    cost = (
        Decimal(totals["input"]) * input_price
        + Decimal(totals["output"]) * output_price
    ) / Decimal(1_000_000)
    return {
        "mode": report["mode"],
        "model": report["model"],
        "input_tokens": totals["input"],
        "output_tokens": totals["output"],
        "price_version": "2026-09-plan-v1",
        "calculated_cost_usd": str(cost.quantize(Decimal("0.000001"))),
        "billing_status": "non_billable_fake"
        if report["mode"] == "fake"
        else "estimated_from_reported_tokens",
    }
