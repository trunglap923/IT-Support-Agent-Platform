"""Shared opaque cursor contract for keyset-paginated API collections."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import HTTPException, Query, status
from pydantic import BaseModel

PageLimit = Annotated[int, Query(ge=1, le=100)]


class CursorItem(Protocol):
    id: UUID


@dataclass(frozen=True)
class CursorPosition:
    timestamp: datetime
    item_id: UUID


class CursorPage[ResponseT](BaseModel):
    items: list[ResponseT]
    next_cursor: str | None


def encode_cursor(timestamp: datetime, item_id: UUID) -> str:
    payload = json.dumps(
        {"v": 1, "ts": timestamp.isoformat(), "id": str(item_id)},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(value: str | None) -> CursorPosition | None:
    if value is None:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        payload = json.loads(base64.b64decode(value + padding, altchars=b"-_", validate=True))
        if not isinstance(payload, dict):
            raise ValueError
        if payload.get("v") != 1:
            raise ValueError
        timestamp = datetime.fromisoformat(payload["ts"])
        if timestamp.tzinfo is None:
            raise ValueError
        return CursorPosition(timestamp=timestamp, item_id=UUID(payload["id"]))
    except (binascii.Error, KeyError, TypeError, ValueError, UnicodeDecodeError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_cursor", "message": "Cursor is invalid"},
        ) from error


def build_page[CursorItemT: CursorItem](
    values: list[CursorItemT],
    *,
    limit: int,
    timestamp: Callable[[CursorItemT], datetime],
) -> tuple[list[CursorItemT], str | None]:
    items = values[:limit]
    next_cursor = None
    if len(values) > limit and items:
        last = items[-1]
        next_cursor = encode_cursor(timestamp(last), last.id)
    return items, next_cursor
