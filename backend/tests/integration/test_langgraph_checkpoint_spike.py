import os

import pytest

from app.agent.checkpoint_spike import run_recovery_probe


def test_pause_restart_and_resume_with_postgres() -> None:
    database_url = os.getenv("CHECKPOINT_DATABASE_URL")
    if not database_url:
        pytest.skip("CHECKPOINT_DATABASE_URL is not configured")

    result = run_recovery_probe(database_url=database_url)

    assert result.pause_process_id != result.resume_process_id
    assert result.paused_status == "paused"
    assert result.resumed_status == "approved"
    assert result.approved is True
