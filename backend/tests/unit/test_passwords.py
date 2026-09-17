import pytest

from app.auth.passwords import hash_password, validate_password, verify_password


def test_password_is_argon2_hashed_and_verifiable() -> None:
    encoded = hash_password("correct-horse-battery-staple")

    assert encoded.startswith("$argon2")
    assert encoded != "correct-horse-battery-staple"
    assert verify_password("correct-horse-battery-staple", encoded) is True
    assert verify_password("wrong-password", encoded) is False


def test_short_password_is_rejected() -> None:
    with pytest.raises(ValueError, match="12 characters"):
        hash_password("too-short")

    with pytest.raises(ValueError, match="12 characters"):
        validate_password("too-short")
