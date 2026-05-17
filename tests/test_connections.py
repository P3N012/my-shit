"""
Stripe Connect OAuth + /connections endpoint coverage.

The Stripe SDK is monkeypatched (`stripe.OAuth.token`, `stripe.Account.retrieve`,
`stripe.OAuth.deauthorize`) so tests run offline without real API keys.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.platform_connection import (
    CONN_ACTIVE,
    OAuthState,
    PlatformConnection,
)


def _auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _full_headers(tokens: dict, org_id: int) -> dict:
    return {**_auth_header(tokens), "X-Organization-Id": str(org_id)}


@pytest.fixture
def org_id(client, auth_tokens):
    me = client.get("/api/v1/auth/me", headers=_auth_header(auth_tokens)).json()
    return me["memberships"][0]["organization_id"]


@pytest.fixture
def stripe_configured():
    """Most tests assume Stripe is configured; flip it on for the test."""
    from app.core import config

    saved_secret = config.settings.STRIPE_SECRET_KEY
    saved_client = config.settings.STRIPE_CONNECT_CLIENT_ID
    config.settings.STRIPE_SECRET_KEY = "sk_test_dummy"
    config.settings.STRIPE_CONNECT_CLIENT_ID = "ca_test_dummy"
    try:
        yield
    finally:
        config.settings.STRIPE_SECRET_KEY = saved_secret
        config.settings.STRIPE_CONNECT_CLIENT_ID = saved_client


# ---------------------------------------------------------------------------
# POST /connections/stripe/connect
# ---------------------------------------------------------------------------

def test_stripe_connect_returns_authorization_url(
    client, auth_tokens, org_id, stripe_configured, db_session
):
    r = client.post(
        "/api/v1/connections/stripe/connect",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["authorization_url"].startswith("https://connect.stripe.com/oauth/authorize")
    assert "client_id=ca_test_dummy" in body["authorization_url"]
    assert "state=" in body["authorization_url"]
    assert "scope=read_write" in body["authorization_url"]
    # State row got persisted
    states = db_session.query(OAuthState).all()
    assert len(states) == 1
    assert states[0].state == body["state"]
    assert states[0].organization_id == org_id


def test_stripe_connect_returns_503_when_unconfigured(client, auth_tokens, org_id):
    from app.core import config

    saved = config.settings.STRIPE_CONNECT_CLIENT_ID
    config.settings.STRIPE_CONNECT_CLIENT_ID = ""
    try:
        r = client.post(
            "/api/v1/connections/stripe/connect",
            headers=_full_headers(auth_tokens, org_id),
        )
        assert r.status_code == 503
    finally:
        config.settings.STRIPE_CONNECT_CLIENT_ID = saved


def test_stripe_connect_requires_org_header(client, auth_tokens, stripe_configured):
    r = client.post(
        "/api/v1/connections/stripe/connect",
        headers=_auth_header(auth_tokens),
    )
    assert r.status_code == 400


def test_stripe_connect_requires_auth(client, org_id, stripe_configured):
    r = client.post(
        "/api/v1/connections/stripe/connect",
        headers={"X-Organization-Id": str(org_id)},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /connections/stripe/callback
# ---------------------------------------------------------------------------

def test_callback_with_invalid_state_redirects_to_failure(client, stripe_configured):
    r = client.get(
        "/api/v1/connections/stripe/callback",
        params={"code": "ac_test_x", "state": "nope"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "stripe=error" in r.headers["location"]
    assert "Invalid+or+expired+state" in r.headers["location"] or "Invalid" in r.headers["location"]


def test_callback_with_user_denial_redirects_to_failure(client, stripe_configured):
    r = client.get(
        "/api/v1/connections/stripe/callback",
        params={"error": "access_denied", "error_description": "user_denied"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "stripe=error" in r.headers["location"]
    assert "user_denied" in r.headers["location"]


def test_callback_with_missing_params_redirects_to_failure(client, stripe_configured):
    r = client.get(
        "/api/v1/connections/stripe/callback", follow_redirects=False
    )
    assert r.status_code == 302
    assert "missing_code_or_state" in r.headers["location"]


def test_callback_consumes_state_and_creates_connection(
    client, auth_tokens, org_id, stripe_configured, db_session
):
    # Step 1: mint state via /connect
    init = client.post(
        "/api/v1/connections/stripe/connect",
        headers=_full_headers(auth_tokens, org_id),
    ).json()
    state = init["state"]

    # Step 2: mock the Stripe token exchange + account lookup
    fake_token_response = {
        "stripe_user_id": "acct_test_123",
        "access_token": "sk_test_connected_xxx",
        "refresh_token": "rt_test_xxx",
        "scope": "read_only",
        "livemode": False,
    }
    fake_account = MagicMock()
    fake_account.get.side_effect = lambda k, default=None: {
        "business_profile": {"name": "Acme Coffee Co."},
        "country": "US",
        "default_currency": "usd",
        "settings": {},
        "email": "ops@acme.test",
    }.get(k, default)

    with patch(
        "app.services.stripe_oauth_service.stripe.OAuth.token",
        return_value=fake_token_response,
    ), patch(
        "app.services.stripe_oauth_service.stripe.Account.retrieve",
        return_value=fake_account,
    ):
        r = client.get(
            "/api/v1/connections/stripe/callback",
            params={"code": "ac_test_x", "state": state},
            follow_redirects=False,
        )

    assert r.status_code == 302
    assert "stripe=ok" in r.headers["location"]
    assert "connection_id=" in r.headers["location"]

    # State row was consumed (one-time use)
    assert db_session.query(OAuthState).count() == 0

    # Connection row exists, scoped to the right org, with no token leakage in the redirect
    conns = (
        db_session.query(PlatformConnection)
        .filter(PlatformConnection.organization_id == org_id)
        .all()
    )
    assert len(conns) == 1
    c = conns[0]
    assert c.platform == "stripe"
    assert c.account_id == "acct_test_123"
    assert c.access_token == "sk_test_connected_xxx"
    assert c.refresh_token == "rt_test_xxx"
    assert c.status == CONN_ACTIVE
    assert c.account_name == "Acme Coffee Co."
    assert c.account_metadata["country"] == "US"


def test_callback_with_stripe_rejection_redirects_to_failure(
    client, auth_tokens, org_id, stripe_configured, db_session
):
    init = client.post(
        "/api/v1/connections/stripe/connect",
        headers=_full_headers(auth_tokens, org_id),
    ).json()

    import stripe as stripe_lib

    with patch(
        "app.services.stripe_oauth_service.stripe.OAuth.token",
        side_effect=stripe_lib.oauth_error.OAuthError("invalid_grant", "bad code"),
    ):
        r = client.get(
            "/api/v1/connections/stripe/callback",
            params={"code": "ac_x", "state": init["state"]},
            follow_redirects=False,
        )

    assert r.status_code == 302
    assert "stripe=error" in r.headers["location"]
    # State should still be consumed even on failure (prevents replay)
    assert db_session.query(OAuthState).count() == 0


def test_callback_with_expired_state_fails(
    client, auth_tokens, org_id, stripe_configured, db_session
):
    """A state token older than its TTL is rejected like an invalid one."""
    state_value = "stale-token"
    db_session.add(
        OAuthState(
            state=state_value,
            platform="stripe",
            user_id=1,
            organization_id=org_id,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    db_session.commit()

    r = client.get(
        "/api/v1/connections/stripe/callback",
        params={"code": "ac_x", "state": state_value},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "stripe=error" in r.headers["location"]


def test_second_callback_for_same_account_updates_existing(
    client, auth_tokens, org_id, stripe_configured, db_session
):
    """Reconnecting Stripe must refresh tokens, not create a duplicate row."""
    fake_token_response = {
        "stripe_user_id": "acct_dupe",
        "access_token": "sk_test_v1",
        "refresh_token": "rt_v1",
        "scope": "read_only",
        "livemode": False,
    }

    for new_token in ("sk_test_v1", "sk_test_v2"):
        init = client.post(
            "/api/v1/connections/stripe/connect",
            headers=_full_headers(auth_tokens, org_id),
        ).json()
        fake_token_response["access_token"] = new_token
        with patch(
            "app.services.stripe_oauth_service.stripe.OAuth.token",
            return_value=dict(fake_token_response),
        ), patch(
            "app.services.stripe_oauth_service.stripe.Account.retrieve",
            side_effect=Exception("account lookup unavailable"),
        ):
            r = client.get(
                "/api/v1/connections/stripe/callback",
                params={"code": "ac", "state": init["state"]},
                follow_redirects=False,
            )
            assert r.status_code == 302

    conns = (
        db_session.query(PlatformConnection)
        .filter(PlatformConnection.organization_id == org_id)
        .all()
    )
    assert len(conns) == 1, "Reconnect must not duplicate the row"
    assert conns[0].access_token == "sk_test_v2", "Tokens must be refreshed on reconnect"


# ---------------------------------------------------------------------------
# GET /connections, GET/DELETE /connections/{id}
# ---------------------------------------------------------------------------

def _seed_connection(db_session, org_id, **overrides) -> PlatformConnection:
    defaults = dict(
        organization_id=org_id,
        platform="stripe",
        account_id="acct_seeded",
        account_name="Seed Co.",
        access_token="sk_test_seed",
        refresh_token="rt_seed",
        status=CONN_ACTIVE,
    )
    defaults.update(overrides)
    conn = PlatformConnection(**defaults)
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)
    return conn


def test_list_connections_returns_org_connections_only(
    client, auth_tokens, org_id, db_session
):
    _seed_connection(db_session, org_id, account_id="acct_a")
    _seed_connection(db_session, org_id, account_id="acct_b")
    _seed_connection(db_session, 999, account_id="acct_other_org")

    r = client.get(
        "/api/v1/connections", headers=_full_headers(auth_tokens, org_id)
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    account_ids = {c["account_id"] for c in body["connections"]}
    assert account_ids == {"acct_a", "acct_b"}


def test_list_response_never_includes_tokens(client, auth_tokens, org_id, db_session):
    """Sensitive fields must not leak through the API response."""
    _seed_connection(db_session, org_id)
    r = client.get(
        "/api/v1/connections", headers=_full_headers(auth_tokens, org_id)
    )
    body = r.json()
    payload = repr(body)
    assert "sk_test_seed" not in payload
    assert "rt_seed" not in payload
    for c in body["connections"]:
        assert "access_token" not in c
        assert "refresh_token" not in c


def test_get_connection_returns_one(client, auth_tokens, org_id, db_session):
    conn = _seed_connection(db_session, org_id)
    r = client.get(
        f"/api/v1/connections/{conn.id}",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.status_code == 200
    assert r.json()["account_id"] == "acct_seeded"


def test_get_connection_404s_cross_org(client, auth_tokens, org_id, db_session):
    other_conn = _seed_connection(db_session, 999, account_id="acct_other")
    r = client.get(
        f"/api/v1/connections/{other_conn.id}",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.status_code == 404


def test_delete_connection_removes_it(
    client, auth_tokens, org_id, stripe_configured, db_session
):
    conn = _seed_connection(db_session, org_id)
    with patch(
        "app.services.stripe_oauth_service.stripe.OAuth.deauthorize",
        return_value=MagicMock(),
    ):
        r = client.delete(
            f"/api/v1/connections/{conn.id}",
            headers=_full_headers(auth_tokens, org_id),
        )
    assert r.status_code == 200
    assert (
        db_session.query(PlatformConnection)
        .filter(PlatformConnection.id == conn.id)
        .first()
        is None
    )


def test_delete_connection_404s_cross_org(
    client, auth_tokens, org_id, stripe_configured, db_session
):
    other_conn = _seed_connection(db_session, 999, account_id="acct_other")
    r = client.delete(
        f"/api/v1/connections/{other_conn.id}",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.status_code == 404
    # And the foreign row is still there
    assert (
        db_session.query(PlatformConnection)
        .filter(PlatformConnection.id == other_conn.id)
        .first()
        is not None
    )
