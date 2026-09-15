"""Trusted principal built from a current database session."""

from dataclasses import dataclass
from uuid import UUID

from app.db.models import UserRole


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: UUID
    session_id: UUID
    email: str
    display_name: str
    role: UserRole
    department_id: UUID
    department_key: str
