"""Encryption-at-rest for connected-account OAuth tokens.

Locks in the trust-critical property: tokens are ciphertext in the
database and plaintext only inside the application.
"""

import sqlalchemy as sa

from app.core.crypto import decrypt, encrypt, is_encrypted
from app.models.platform_connection import PLATFORM_STRIPE, PlatformConnection


# ---------------------------------------------------------------------------
# Primitive round-trip
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_round_trip():
    secret = "sk_live_super_secret_token_value"
    ciphertext = encrypt(secret)
    assert ciphertext != secret
    assert secret not in ciphertext
    assert decrypt(ciphertext) == secret


def test_encrypt_is_non_deterministic():
    # Fernet embeds a random IV + timestamp, so the same input encrypts
    # to different ciphertext each time but decrypts back identically.
    secret = "token"
    assert encrypt(secret) != encrypt(secret)
    assert decrypt(encrypt(secret)) == secret


def test_decrypt_tolerates_legacy_plaintext():
    # A value written before encryption existed isn't valid ciphertext;
    # decrypt should return it unchanged rather than raise.
    assert decrypt("legacy_plaintext_token") == "legacy_plaintext_token"


def test_is_encrypted():
    assert is_encrypted(encrypt("x")) is True
    assert is_encrypted("not-ciphertext") is False


# ---------------------------------------------------------------------------
# Column behaviour: ciphertext at rest, plaintext via the ORM
# ---------------------------------------------------------------------------

def test_token_is_ciphertext_at_rest(db_session):
    secret = "sk_live_at_rest_check"
    conn = PlatformConnection(
        organization_id=1,
        user_id=None,
        platform=PLATFORM_STRIPE,
        account_id="acct_test_at_rest",
        access_token=secret,
        refresh_token="rt_secret_value",
    )
    db_session.add(conn)
    db_session.commit()

    # Raw column read bypasses the ORM type — it must be ciphertext.
    raw = db_session.execute(
        sa.text("SELECT access_token, refresh_token FROM platform_connections WHERE id = :id"),
        {"id": conn.id},
    ).one()
    assert raw.access_token != secret
    assert secret not in raw.access_token
    assert "rt_secret_value" not in raw.refresh_token

    # Reading back through the ORM decrypts transparently.
    db_session.expire_all()
    fresh = db_session.get(PlatformConnection, conn.id)
    assert fresh.access_token == secret
    assert fresh.refresh_token == "rt_secret_value"


def test_null_refresh_token_stays_null(db_session):
    conn = PlatformConnection(
        organization_id=1,
        user_id=None,
        platform=PLATFORM_STRIPE,
        account_id="acct_test_null_rt",
        access_token="at_value",
        refresh_token=None,
    )
    db_session.add(conn)
    db_session.commit()
    db_session.expire_all()
    fresh = db_session.get(PlatformConnection, conn.id)
    assert fresh.refresh_token is None
