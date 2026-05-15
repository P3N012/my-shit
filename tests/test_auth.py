"""End-to-end coverage of /auth/* routes and the auth service.

The intent is to lock in the security properties surfaced in the
previous review: refresh-token rotation, refresh-token reuse rejection,
and at-rest hashing of refresh tokens.
"""

import hashlib
import time

from app.models.user import RefreshToken, User


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def test_register_creates_user(client):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "a@b.com",
            "username": "alice",
            "password": "password123",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "a@b.com"
    assert body["username"] == "alice"
    assert "id" in body


def test_register_persists_hashed_password(client, db_session):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "a@b.com",
            "username": "alice",
            "password": "password123",
        },
    )
    user = db_session.query(User).filter(User.email == "a@b.com").one()
    assert user.password_hash != "password123"
    assert user.password_hash.startswith("$2")  # bcrypt prefix


def test_register_rejects_duplicate_email(client, registered_user):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": registered_user["email"],
            "username": "different",
            "password": "password123",
        },
    )
    assert r.status_code == 400
    assert "email" in r.json()["detail"].lower()


def test_register_rejects_duplicate_username(client, registered_user):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "different@example.com",
            "username": registered_user["username"],
            "password": "password123",
        },
    )
    assert r.status_code == 400
    assert "username" in r.json()["detail"].lower()


def test_register_rejects_short_password(client):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "a@b.com",
            "username": "alice",
            "password": "short",
        },
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_returns_tokens(client, registered_user):
    r = client.post(
        "/api/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["access_token"] != body["refresh_token"]


def test_login_rejects_bad_password(client, registered_user):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "wrong"},
    )
    assert r.status_code == 401


def test_login_rejects_unknown_email(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------

def test_me_returns_current_user(client, auth_tokens, registered_user):
    r = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {auth_tokens['access_token']}"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == registered_user["email"]


def test_me_requires_token(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 403  # HTTPBearer returns 403 when no header


def test_me_rejects_garbage_token(client):
    r = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Refresh + rotation
# ---------------------------------------------------------------------------

def test_refresh_rotates_token(client, auth_tokens):
    # exp claim is per-second; sleep so the new JWT string differs
    time.sleep(1)
    r = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": auth_tokens["refresh_token"]},
    )
    assert r.status_code == 200
    new = r.json()
    assert new["refresh_token"] != auth_tokens["refresh_token"]
    assert new["access_token"]


def test_refresh_rejects_reuse_of_rotated_token(client, auth_tokens):
    time.sleep(1)
    first = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": auth_tokens["refresh_token"]},
    )
    assert first.status_code == 200
    # Original refresh is now revoked
    reused = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": auth_tokens["refresh_token"]},
    )
    assert reused.status_code == 401


def test_refresh_rejects_unknown_token(client):
    r = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "garbage"}
    )
    assert r.status_code == 401


def test_refresh_tokens_stored_as_hash_not_plaintext(
    client, auth_tokens, db_session
):
    rows = db_session.query(RefreshToken).all()
    assert len(rows) == 1
    row = rows[0]
    # SHA-256 hex digest is exactly 64 chars
    assert len(row.token_hash) == 64
    # And matches the hash of the token returned to the client
    expected = hashlib.sha256(auth_tokens["refresh_token"].encode()).hexdigest()
    assert row.token_hash == expected
    # The raw token must not be stored
    assert auth_tokens["refresh_token"] not in row.token_hash


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout_revokes_refresh(client, auth_tokens):
    r = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": auth_tokens["refresh_token"]},
    )
    assert r.status_code == 204
    # Subsequent refresh fails
    r = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": auth_tokens["refresh_token"]},
    )
    assert r.status_code == 401


def test_logout_with_unknown_token_is_401(client):
    r = client.post(
        "/api/v1/auth/logout", json={"refresh_token": "garbage"}
    )
    assert r.status_code == 401
