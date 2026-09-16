"""Approval lifecycle services."""

from typing import TYPE_CHECKING, Any

from app.services.approvals.service import (
    ApprovalConflictError,
    ApprovalExpiredError,
    ApprovalNotFoundError,
    ApprovalService,
    canonical_argument_hash,
)

if TYPE_CHECKING:
    from app.services.approvals.resume import execute_approval_resume_run


def __getattr__(name: str) -> Any:
    if name == "execute_approval_resume_run":
        from app.services.approvals.resume import execute_approval_resume_run

        return execute_approval_resume_run
    raise AttributeError(name)


__all__ = [
    "ApprovalConflictError",
    "ApprovalExpiredError",
    "ApprovalNotFoundError",
    "ApprovalService",
    "canonical_argument_hash",
    "execute_approval_resume_run",
]
