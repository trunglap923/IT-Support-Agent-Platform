"""Argon2 password hashing boundary."""

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()
_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$wagCPXjifgvUFBzq4hqe3w$"
    "CYaIb8sB+wtD+Vu/P4uod1+Qof8h+1g7bbDlBID48Rc"
)


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def verify_dummy_password(password: str) -> None:
    """Spend an Argon2 verification when an account lookup does not match."""

    _password_hash.verify(password, _DUMMY_HASH)
