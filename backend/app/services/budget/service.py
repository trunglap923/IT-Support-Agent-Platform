"""Atomic admission control for paid provider operations."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy import case, func, select, text

from app.db import Database
from app.db.models import UsageLedgerEntry, UsageStatus


class BudgetExceededError(RuntimeError):
    pass


class DuplicateOperationError(RuntimeError):
    pass


class DatabaseUsageLedger:
    def __init__(
        self,
        database: Database,
        *,
        daily_budget_usd: Decimal,
        monthly_budget_usd: Decimal,
        input_price_per_million_usd: Decimal,
        price_version: str,
        output_price_per_million_usd: Decimal = Decimal("0"),
    ) -> None:
        self._database = database
        self._daily_budget = daily_budget_usd
        self._monthly_budget = monthly_budget_usd
        self._input_price = input_price_per_million_usd
        self._output_price = output_price_per_million_usd
        self._price_version = price_version

    def cost_for_tokens(self, tokens: int) -> Decimal:
        return (Decimal(tokens) * self._input_price / Decimal(1_000_000)).quantize(
            Decimal("0.00000001")
        )

    def cost_for_usage(self, input_tokens: int, output_tokens: int = 0) -> Decimal:
        value = (
            Decimal(input_tokens) * self._input_price + Decimal(output_tokens) * self._output_price
        ) / Decimal(1_000_000)
        return value.quantize(Decimal("0.00000001"))

    async def reserve(
        self,
        *,
        operation_id: str,
        provider: str,
        model: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int = 0,
        kind: str = "embedding",
    ) -> None:
        if estimated_input_tokens <= 0:
            raise ValueError("estimated_input_tokens must be positive")
        now = datetime.now(UTC)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if estimated_output_tokens < 0:
            raise ValueError("estimated_output_tokens cannot be negative")
        reserved_cost = self.cost_for_usage(estimated_input_tokens, estimated_output_tokens)
        effective_cost = case(
            (
                UsageLedgerEntry.status == UsageStatus.COMPLETED.value,
                UsageLedgerEntry.actual_cost_usd,
            ),
            else_=UsageLedgerEntry.reserved_cost_usd,
        )
        async with self._database.session() as session, session.begin():
            await session.execute(text("SELECT pg_advisory_xact_lock(hashtext('ai-usage-budget'))"))
            if await session.scalar(
                select(UsageLedgerEntry.id).where(UsageLedgerEntry.operation_id == operation_id)
            ):
                raise DuplicateOperationError(f"Operation {operation_id!r} already exists")
            daily = cast(
                Decimal,
                await session.scalar(
                    select(func.coalesce(func.sum(effective_cost), 0)).where(
                        UsageLedgerEntry.created_at >= day_start
                    )
                ),
            )
            monthly = cast(
                Decimal,
                await session.scalar(
                    select(func.coalesce(func.sum(effective_cost), 0)).where(
                        UsageLedgerEntry.created_at >= month_start
                    )
                ),
            )
            if daily + reserved_cost > self._daily_budget:
                raise BudgetExceededError("Daily AI budget would be exceeded")
            if monthly + reserved_cost > self._monthly_budget:
                raise BudgetExceededError("Monthly AI budget would be exceeded")
            session.add(
                UsageLedgerEntry(
                    operation_id=operation_id,
                    kind=kind,
                    provider=provider,
                    model=model,
                    price_version=self._price_version,
                    status=UsageStatus.RESERVED.value,
                    reserved_input_tokens=estimated_input_tokens,
                    reserved_output_tokens=estimated_output_tokens,
                    reserved_cost_usd=reserved_cost,
                )
            )

    async def complete(
        self,
        *,
        operation_id: str,
        actual_input_tokens: int,
        actual_output_tokens: int = 0,
        provider_request_id: str,
    ) -> None:
        async with self._database.session() as session, session.begin():
            entry = await session.scalar(
                select(UsageLedgerEntry)
                .where(UsageLedgerEntry.operation_id == operation_id)
                .with_for_update()
            )
            if entry is None:
                raise LookupError(f"No usage reservation for {operation_id!r}")
            entry.status = UsageStatus.COMPLETED.value
            entry.actual_input_tokens = actual_input_tokens
            entry.actual_output_tokens = actual_output_tokens
            entry.actual_cost_usd = self.cost_for_usage(actual_input_tokens, actual_output_tokens)
            entry.provider_request_id = provider_request_id

    async def mark_unknown(self, *, operation_id: str) -> None:
        async with self._database.session() as session, session.begin():
            entry = await session.scalar(
                select(UsageLedgerEntry)
                .where(UsageLedgerEntry.operation_id == operation_id)
                .with_for_update()
            )
            if entry is not None and entry.status == UsageStatus.RESERVED.value:
                entry.status = UsageStatus.UNKNOWN.value
