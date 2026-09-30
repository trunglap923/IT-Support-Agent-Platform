from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.pagination import decode_cursor, encode_cursor


def test_cursor_round_trip_preserves_timestamp_and_id() -> None:
    timestamp = datetime(2026, 9, 30, 4, 15, 30, 123456, tzinfo=UTC)
    item_id = uuid4()

    decoded = decode_cursor(encode_cursor(timestamp, item_id))

    assert decoded is not None
    assert decoded.timestamp == timestamp
    assert decoded.item_id == item_id


@pytest.mark.parametrize("cursor", ["bad", "W10", "e30", "eyJ2IjoyfQ"])
def test_invalid_cursor_is_rejected(cursor: str) -> None:
    with pytest.raises(HTTPException) as raised:
        decode_cursor(cursor)

    assert raised.value.status_code == 422
    assert raised.value.detail["code"] == "invalid_cursor"
