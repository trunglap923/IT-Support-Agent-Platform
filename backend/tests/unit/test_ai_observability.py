from decimal import Decimal

from app.config import Settings
from app.observability import NoopAIObserver, create_ai_observer
from app.services.budget.service import DatabaseUsageLedger


def test_fake_mode_observability_requires_no_keys() -> None:
    observer = create_ai_observer(Settings(langfuse_public_key=None, langfuse_secret_key=None))
    assert isinstance(observer, NoopAIObserver)
    with observer.generation(
        run_id="run-1",
        actor_id="user-1",
        model="fake",
        evidence_count=2,
    ) as observation:
        assert observation is None


def test_usage_cost_accounts_for_input_and_output_tokens() -> None:
    ledger = DatabaseUsageLedger(
        None,  # type: ignore[arg-type]
        daily_budget_usd=Decimal("1"),
        monthly_budget_usd=Decimal("10"),
        input_price_per_million_usd=Decimal("0.40"),
        output_price_per_million_usd=Decimal("1.60"),
        price_version="test",
    )
    assert ledger.cost_for_usage(1_000_000, 1_000_000) == Decimal("2.00000000")
