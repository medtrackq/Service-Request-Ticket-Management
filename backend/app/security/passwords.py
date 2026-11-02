"""Password hashing with Argon2id (argon2-cffi defaults follow RFC 9106 recommendations)."""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

# Pre-computed hash used to keep login timing similar for unknown usernames.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_policy_errors(password: str, min_length: int) -> list[str]:
    errors = []
    if len(password) < min_length:
        errors.append(f"รหัสผ่านต้องมีอย่างน้อย {min_length} ตัวอักษร")
    if password.isdigit() or password.isalpha():
        errors.append("รหัสผ่านต้องมีทั้งตัวอักษรและตัวเลขหรือสัญลักษณ์")
    if len(password) > 128:
        errors.append("รหัสผ่านยาวเกินไป")
    return errors
