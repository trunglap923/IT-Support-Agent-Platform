import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db import Database
from app.db.models import UsageLedgerEntry, UsageStatus
from app.services.budget.service import BudgetExceededError, DatabaseUsageLedger


def test_usage_is_reserved_before_completion_and_budget_counts_it(
    migrated_database_url: str,
) -> None:
    async def scenario() -> None:
        database = Database(migrated_database_url)
        ledger = DatabaseUsageLedger(
            database,
            daily_budget_usd=Decimal("2"),
            monthly_budget_usd=Decimal("2"),
            input_price_per_million_usd=Decimal("1000000"),
            price_version="test-v1",
        )
        try:
            await ledger.reserve(
                operation_id="embed-1",
                provider="openai",
                model="test-model",
                estimated_input_tokens=1,
            )
            async with database.session() as session:
                entry = await session.scalar(
                    select(UsageLedgerEntry).where(UsageLedgerEntry.operation_id == "embed-1")
                )
                assert entry is not None
                assert entry.status == UsageStatus.RESERVED.value
            await ledger.complete(
                operation_id="embed-1",
                actual_input_tokens=1,
                provider_request_id="provider-1",
            )
            with pytest.raises(BudgetExceededError):
                await ledger.reserve(
                    operation_id="embed-2",
                    provider="openai",
                    model="test-model",
                    estimated_input_tokens=2,
                )
        finally:
            await database.close()

    asyncio.run(scenario())
