"""Run deterministic or explicitly enabled live agent evaluations."""

from __future__ import annotations

import argparse
import asyncio
import os
from decimal import Decimal
from pathlib import Path

from app.config import AIProvider, Settings
from app.db import Database
from app.providers import StructuredResponseProvider, create_provider
from app.providers.fake import FakeTextProvider
from evals.runner.harness import CaseRun, execute_case
from evals.runner.load_cases import dataset_digest, load_cases, select_cases
from evals.runner.report import build_report, write_report

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "reports" / "raw" / "agent-evaluation.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fake", "live"), default="fake")
    parser.add_argument("--split", choices=("development", "holdout", "all"), default="development")
    parser.add_argument(
        "--category",
        choices=("rag", "permission", "tool", "approval", "memory", "failure"),
    )
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260916)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def _positive(value: int | None, name: str) -> None:
    if value is not None and value <= 0:
        raise SystemExit(f"{name} must be positive")


async def run(args: argparse.Namespace) -> dict[str, object]:
    _positive(args.max_cases, "--max-cases")
    _positive(args.repetitions, "--repetitions")
    selected = select_cases(
        load_cases(args.split),
        category=args.category,
        max_cases=args.max_cases,
        seed=args.seed,
    )
    if not selected:
        raise SystemExit("No cases matched the selection")

    provider: StructuredResponseProvider = FakeTextProvider()
    database: Database | None = None
    model = "deterministic-contract-v1"
    max_output_tokens = 160
    run_configuration: dict[str, object] = {
        "category": args.category,
        "max_cases": args.max_cases,
        "repetitions": args.repetitions,
        "live_opt_in": False,
    }
    if args.mode == "live":
        if os.getenv("RUN_LIVE_EVAL") != "1":
            raise SystemExit("Live evaluation requires RUN_LIVE_EVAL=1")
        quota = int(os.getenv("EVAL_LIVE_MAX_CALLS", "5"))
        _positive(quota, "EVAL_LIVE_MAX_CALLS")
        rag_calls = sum(case.category == "rag" for case in selected) * args.repetitions
        if rag_calls > quota:
            raise SystemExit(f"Live RAG calls {rag_calls} exceed EVAL_LIVE_MAX_CALLS={quota}")
        requested_output_tokens = int(os.getenv("EVAL_LIVE_MAX_OUTPUT_TOKENS", "160"))
        _positive(requested_output_tokens, "EVAL_LIVE_MAX_OUTPUT_TOKENS")
        max_output_tokens = min(requested_output_tokens, 200)
        settings = Settings()
        if settings.ai_provider is not AIProvider.OPENAI:
            raise SystemExit("Live evaluation requires AI_PROVIDER=openai")
        database_url = os.getenv("EVAL_DATABASE_URL")
        if not database_url:
            raise SystemExit("Live evaluation requires a migrated EVAL_DATABASE_URL")
        estimated_input_tokens = (
            sum(
                500
                + sum(len(message["content"]) for message in case.messages) // 4
                + sum(len(item["span"]) for item in case.relevant_evidence) // 4
                for case in selected
                if case.category == "rag"
            )
            * args.repetitions
        )
        estimated_cost = (
            Decimal(estimated_input_tokens)
            * Decimal(str(settings.openai_input_price_per_million_usd))
            + Decimal(rag_calls * max_output_tokens)
            * Decimal(str(settings.openai_output_price_per_million_usd))
        ) / Decimal(1_000_000)
        max_estimated_cost = Decimal(os.getenv("EVAL_LIVE_MAX_ESTIMATED_USD", "0.05"))
        if estimated_cost > max_estimated_cost:
            raise SystemExit("Estimated live cost exceeds EVAL_LIVE_MAX_ESTIMATED_USD")
        database = Database(database_url)
        provider = create_provider(settings, database)
        model = settings.openai_model
        run_configuration.update(
            {
                "live_opt_in": True,
                "max_provider_calls": quota,
                "planned_provider_calls": rag_calls,
                "max_output_tokens_per_call": max_output_tokens,
                "estimated_input_tokens": estimated_input_tokens,
                "estimated_cost_usd": str(estimated_cost.quantize(Decimal("0.000001"))),
                "max_estimated_cost_usd": str(max_estimated_cost),
            }
        )

    run_id = f"{args.mode}-{args.split}-{args.seed}"
    results: list[CaseRun] = []
    try:
        for repetition in range(1, args.repetitions + 1):
            for case in selected:
                results.append(
                    await execute_case(
                        case,
                        repetition=repetition,
                        provider=provider,
                        run_id=run_id,
                        max_output_tokens=max_output_tokens,
                    )
                )
    finally:
        await provider.close()
        if database is not None:
            await database.close()

    report = build_report(
        mode=args.mode,
        model=model,
        split=args.split,
        seed=args.seed,
        dataset_sha256=dataset_digest(selected),
        document_snapshots=[case.document_snapshot for case in selected],
        run_configuration=run_configuration,
        runs=results,
        root=ROOT,
    )
    write_report(report, args.output)
    return report


def main() -> None:
    args = parse_args()
    report = asyncio.run(run(args))
    passed = report["deterministic_pass"]
    print(
        f"Evaluation complete: {passed['numerator']}/{passed['denominator']} deterministic checks; "
        f"artifact={args.output}"
    )
    if passed["numerator"] != passed["denominator"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
