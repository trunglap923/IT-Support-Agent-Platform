import pytest

from app.db.models import RunStatus
from app.services.conversations.run_state import (
    TERMINAL_RUN_STATUSES,
    InvalidRunTransitionError,
    validate_run_transition,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (RunStatus.QUEUED, RunStatus.RUNNING),
        (RunStatus.QUEUED, RunStatus.CANCELLED),
        (RunStatus.RUNNING, RunStatus.WAITING_APPROVAL),
        (RunStatus.RUNNING, RunStatus.COMPLETED),
        (RunStatus.RUNNING, RunStatus.FAILED),
        (RunStatus.WAITING_APPROVAL, RunStatus.RESUME_QUEUED),
        (RunStatus.WAITING_APPROVAL, RunStatus.COMPLETED),
        (RunStatus.WAITING_APPROVAL, RunStatus.CANCELLED),
        (RunStatus.RESUME_QUEUED, RunStatus.RUNNING),
    ],
)
def test_valid_run_transitions(current: RunStatus, target: RunStatus) -> None:
    validate_run_transition(current, target)


@pytest.mark.parametrize("terminal", TERMINAL_RUN_STATUSES)
def test_terminal_states_reject_further_transitions(terminal: RunStatus) -> None:
    with pytest.raises(InvalidRunTransitionError):
        validate_run_transition(terminal, RunStatus.RUNNING)


def test_running_run_cannot_be_cancelled() -> None:
    with pytest.raises(InvalidRunTransitionError):
        validate_run_transition(RunStatus.RUNNING, RunStatus.CANCELLED)
