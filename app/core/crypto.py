"""
Symmetric encryption for sensitive values stored at rest — currently the
OAuth access/refresh tokens for connected Stripe accounts.

Uses Fernet (AES-128-CBC + HMAC-SHA256, from `cryptography`). The key is
read from `TOKEN_ENCRYPTION_KEY` when set; otherwise it's derived
deterministically from `ACCESS_TOKEN_SECRET` so the app works out of the
box. Production should set a dedicated `TOKEN_ENCRYPTION_KEY` — generate
one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

`EncryptedString` is a SQLAlchemy column type that encrypts on write and
decrypts on read, so application code keeps reading the column as plain
text and never sees ciphertext.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import Text, TypeDecorator

from app.core.config import settings


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = settings.TOKEN_ENCRYPTION_KEY.strip()
    if key:
        # Expect a urlsafe-base64 32-byte Fernet key.
        return Fernet(key.encode())
    # No dedicated key configured: derive a stable 32-byte key from the
    # access-token secret so encryption works without extra setup.
    digest = hashlib.sha256(settings.ACCESS_TOKEN_SECRET.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext: str) -> str:
    """Encrypt a string, returning urlsafe-base64 ciphertext."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(value: str) -> str:
    """
    Decrypt a value. Tolerates legacy plaintext: if `value` isn't valid
    Fernet ciphertext it's returned unchanged, so rows written before
    encryption was introduced keep working until the migration rewrites
    them.
    """
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError):
        return value


def is_encrypted(value: str) -> bool:
    """True if `value` is decryptable Fernet ciphertext under the current key."""
    try:
        _fernet().decrypt(value.encode())
        return True
    except (InvalidToken, ValueError):
        return False


class EncryptedString(TypeDecorator):
    """A text column transparently encrypted at rest with Fernet."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt(value)
