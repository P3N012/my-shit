"""
Security utilities

- Password hashing and verification (bcrypt)
- JWT access/refresh token creation and decoding
- Opaque-token hashing for at-rest storage of refresh tokens
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# JWTs
# ---------------------------------------------------------------------------

def _encode(data: Dict[str, Any], secret: str, expires: timedelta) -> str:
    to_encode = data.copy()
    to_encode["exp"] = _utcnow() + expires
    return jwt.encode(to_encode, secret, algorithm=settings.ALGORITHM)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    expires = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _encode(data, settings.ACCESS_TOKEN_SECRET, expires)


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    expires = expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _encode(data, settings.REFRESH_TOKEN_SECRET, expires)


def decode_token(token: str, secret: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, secret, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    return decode_token(token, settings.ACCESS_TOKEN_SECRET)


def decode_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    return decode_token(token, settings.REFRESH_TOKEN_SECRET)


def get_user_id_from_token(token: str, is_refresh: bool = False) -> Optional[int]:
    payload = decode_refresh_token(token) if is_refresh else decode_access_token(token)
    if not payload:
        return None
    sub = payload.get("sub")
    try:
        return int(sub) if sub is not None else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Opaque-token hashing (refresh tokens at rest)
# ---------------------------------------------------------------------------
# Refresh tokens are high-entropy JWTs, so a fast hash (sha256) is sufficient
# and avoids paying bcrypt cost on every refresh. The DB only ever stores the
# hash; a leaked DB row cannot be replayed as a valid token.

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
