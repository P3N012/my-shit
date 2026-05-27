"""
StripeSyncService tests.

We monkeypatch `stripe.Customer.list`, `stripe.Subscription.list`, and
`stripe.Charge.list` to return fake objects with `.auto_paging_iter()`
so no network is involved.
"""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import stripe

from app.models.platform_connection import (
    AUTH_RESTRICTED_KEY,
    CONN_ACTIVE,
    CONN_ERROR,
    PLATFORM_STRIPE,
    PlatformConnection,
)
from app.models.stripe_data import (
    SYNC_FAILED,
    SYNC_SUCCESS,
    StripeCharge,
    StripeCustomer,
    StripeSubscription,
    SyncLog,
)
from app.services.stripe_sync_service import StripeSyncService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeList:
    """Mimics stripe's ListObject — exposes auto_paging_iter()."""

    def __init__(self, items):
        self._items = list(items)

    def auto_paging_iter(self):
        return iter(self._items)


def _ts(year: int, month: int, day: int) -> int:
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp())


def _make_connection(db, org_id: int = 1) -> PlatformConnection:
    conn = PlatformConnection(
        organization_id=org_id,
        platform=PLATFORM_STRIPE,
        account_id="acct_sync_test",
        access_token="sk_dummy",
        status=CONN_ACTIVE,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@pytest.fixture(autouse=True)
def stripe_secret_set():
    """Sync requires STRIPE_SECRET_KEY at runtime; set it for all tests."""
    from app.core import config

    saved = config.settings.STRIPE_SECRET_KEY
    config.settings.STRIPE_SECRET_KEY = "sk_test_dummy"
    try:
        yield
    finally:
        config.settings.STRIPE_SECRET_KEY = saved


# ---------------------------------------------------------------------------
# Auth resolution per connection type
# ---------------------------------------------------------------------------

def test_configure_auth_oauth_uses_platform_key_and_account(db_session):
    conn = _make_connection(db_session)  # default auth_method == "oauth"
    kwargs = StripeSyncService._configure_auth(conn)
    assert kwargs == {"stripe_account": "acct_sync_test"}
    assert stripe.api_key == "sk_test_dummy"  # the platform secret


def test_configure_auth_restricted_key_uses_key_directly(db_session):
    conn = PlatformConnection(
        organization_id=1,
        platform=PLATFORM_STRIPE,
        auth_method=AUTH_RESTRICTED_KEY,
        account_id="acct_rk",
        access_token="rk_test_readonly",
        status=CONN_ACTIVE,
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)

    kwargs = StripeSyncService._configure_auth(conn)
    # No stripe_account header — the key authenticates as the account.
    assert kwargs == {}
    assert stripe.api_key == "rk_test_readonly"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def _fake_customer(cid: str, email: str, name: str, created_unix: int) -> dict:
    return {
        "id": cid,
        "email": email,
        "name": name,
        "description": None,
        "currency": "usd",
        "balance": 0,
        "delinquent": False,
        "livemode": False,
        "metadata": {},
        "created": created_unix,
    }


def _fake_subscription(
    sid: str, cid: str, status: str, unit_amount: int, created_unix: int
) -> dict:
    return {
        "id": sid,
        "customer": cid,
        "status": status,
        "currency": "usd",
        "items": {
            "data": [
                {
                    "id": "si_x",
                    "quantity": 1,
                    "price": {
                        "id": "price_x",
                        "unit_amount": unit_amount,
                        "recurring": {"interval": "month", "interval_count": 1},
                    },
                }
            ]
        },
        "current_period_start": created_unix,
        "current_period_end": created_unix + 30 * 86400,
        "cancel_at_period_end": False,
        "canceled_at": None,
        "start_date": created_unix,
        "ended_at": None,
        "trial_end": None,
        "metadata": {},
        "created": created_unix,
    }


def _fake_charge(chid: str, cid: str, amount: int, status: str, created_unix: int) -> dict:
    return {
        "id": chid,
        "customer": cid,
        "amount": amount,
        "amount_refunded": 0,
        "currency": "usd",
        "status": status,
        "paid": status == "succeeded",
        "refunded": False,
        "livemode": False,
        "description": None,
        "failure_code": None,
        "failure_message": None,
        "metadata": {},
        "created": created_unix,
    }


def test_sync_upserts_customers_subscriptions_charges(db_session):
    conn = _make_connection(db_session)
    customers = [
        _fake_customer("cus_a", "a@b.com", "Alice", _ts(2026, 5, 1)),
        _fake_customer("cus_b", "b@c.com", "Bob", _ts(2026, 5, 2)),
    ]
    subs = [
        _fake_subscription("sub_1", "cus_a", "active", 2900, _ts(2026, 5, 1)),
    ]
    charges = [
        _fake_charge("ch_1", "cus_a", 2900, "succeeded", _ts(2026, 5, 10)),
        _fake_charge("ch_2", "cus_a", 2900, "succeeded", _ts(2026, 5, 11)),
    ]

    with patch(
        "app.services.stripe_sync_service.stripe.Customer.list",
        return_value=_FakeList(customers),
    ), patch(
        "app.services.stripe_sync_service.stripe.Subscription.list",
        return_value=_FakeList(subs),
    ), patch(
        "app.services.stripe_sync_service.stripe.Charge.list",
        return_value=_FakeList(charges),
    ):
        log = StripeSyncService.sync(db_session, conn)

    assert log.status == SYNC_SUCCESS
    assert log.stats_json == {"customers": 2, "subscriptions": 1, "charges": 2}
    assert log.finished_at is not None

    cust_rows = (
        db_session.query(StripeCustomer)
        .filter(StripeCustomer.connection_id == conn.id)
        .all()
    )
    assert {c.stripe_customer_id for c in cust_rows} == {"cus_a", "cus_b"}

    sub_rows = (
        db_session.query(StripeSubscription)
        .filter(StripeSubscription.connection_id == conn.id)
        .all()
    )
    assert len(sub_rows) == 1
    assert sub_rows[0].amount_per_period == 2900
    assert sub_rows[0].interval == "month"
    assert sub_rows[0].status == "active"

    charge_rows = (
        db_session.query(StripeCharge)
        .filter(StripeCharge.connection_id == conn.id)
        .all()
    )
    assert {c.stripe_charge_id for c in charge_rows} == {"ch_1", "ch_2"}

    # Connection state was updated
    db_session.refresh(conn)
    assert conn.status == CONN_ACTIVE
    assert conn.last_sync_status == SYNC_SUCCESS
    assert conn.last_synced_at is not None
    assert conn.error_message is None


def test_sync_is_idempotent(db_session):
    """Running twice with the same data should not duplicate rows."""
    conn = _make_connection(db_session)
    customers = [_fake_customer("cus_a", "a@b.com", "Alice", _ts(2026, 5, 1))]
    subs = [_fake_subscription("sub_1", "cus_a", "active", 1000, _ts(2026, 5, 1))]
    charges = [_fake_charge("ch_1", "cus_a", 1000, "succeeded", _ts(2026, 5, 10))]

    def _patch_and_run():
        with patch(
            "app.services.stripe_sync_service.stripe.Customer.list",
            return_value=_FakeList(customers),
        ), patch(
            "app.services.stripe_sync_service.stripe.Subscription.list",
            return_value=_FakeList(subs),
        ), patch(
            "app.services.stripe_sync_service.stripe.Charge.list",
            return_value=_FakeList(charges),
        ):
            return StripeSyncService.sync(db_session, conn)

    _patch_and_run()
    _patch_and_run()

    assert (
        db_session.query(StripeCustomer)
        .filter(StripeCustomer.connection_id == conn.id)
        .count()
        == 1
    )
    assert (
        db_session.query(StripeSubscription)
        .filter(StripeSubscription.connection_id == conn.id)
        .count()
        == 1
    )
    assert (
        db_session.query(StripeCharge)
        .filter(StripeCharge.connection_id == conn.id)
        .count()
        == 1
    )
    # Both runs wrote a sync_log row
    assert (
        db_session.query(SyncLog).filter(SyncLog.connection_id == conn.id).count()
        == 2
    )


def test_sync_updates_existing_rows_on_change(db_session):
    """Second sync with updated data should overwrite the existing row."""
    conn = _make_connection(db_session)

    v1 = [_fake_subscription("sub_1", "cus_a", "active", 1000, _ts(2026, 5, 1))]
    v2 = [_fake_subscription("sub_1", "cus_a", "canceled", 1000, _ts(2026, 5, 1))]

    for batch in (v1, v2):
        with patch(
            "app.services.stripe_sync_service.stripe.Customer.list",
            return_value=_FakeList([]),
        ), patch(
            "app.services.stripe_sync_service.stripe.Subscription.list",
            return_value=_FakeList(batch),
        ), patch(
            "app.services.stripe_sync_service.stripe.Charge.list",
            return_value=_FakeList([]),
        ):
            StripeSyncService.sync(db_session, conn)

    rows = (
        db_session.query(StripeSubscription)
        .filter(StripeSubscription.connection_id == conn.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].status == "canceled"


def test_sync_failure_marks_connection_error(db_session):
    conn = _make_connection(db_session)

    with patch(
        "app.services.stripe_sync_service.stripe.Customer.list",
        side_effect=RuntimeError("stripe is on fire"),
    ):
        with pytest.raises(RuntimeError):
            StripeSyncService.sync(db_session, conn)

    db_session.refresh(conn)
    assert conn.status == CONN_ERROR
    assert conn.last_sync_status == SYNC_FAILED
    assert "stripe is on fire" in (conn.error_message or "")

    log = (
        db_session.query(SyncLog)
        .filter(SyncLog.connection_id == conn.id)
        .order_by(SyncLog.id.desc())
        .first()
    )
    assert log is not None
    assert log.status == SYNC_FAILED
    assert "stripe is on fire" in (log.error or "")


def test_subscription_amount_sums_across_items(db_session):
    """A subscription with two items should report the sum as amount_per_period."""
    conn = _make_connection(db_session)
    sub = {
        "id": "sub_multi",
        "customer": "cus_x",
        "status": "active",
        "currency": "usd",
        "items": {
            "data": [
                {
                    "id": "si_a",
                    "quantity": 2,
                    "price": {
                        "id": "price_a",
                        "unit_amount": 500,
                        "recurring": {"interval": "month", "interval_count": 1},
                    },
                },
                {
                    "id": "si_b",
                    "quantity": 1,
                    "price": {
                        "id": "price_b",
                        "unit_amount": 1500,
                        "recurring": {"interval": "month", "interval_count": 1},
                    },
                },
            ]
        },
        "current_period_start": _ts(2026, 5, 1),
        "current_period_end": _ts(2026, 6, 1),
        "cancel_at_period_end": False,
        "metadata": {},
        "created": _ts(2026, 5, 1),
    }
    with patch(
        "app.services.stripe_sync_service.stripe.Customer.list",
        return_value=_FakeList([]),
    ), patch(
        "app.services.stripe_sync_service.stripe.Subscription.list",
        return_value=_FakeList([sub]),
    ), patch(
        "app.services.stripe_sync_service.stripe.Charge.list",
        return_value=_FakeList([]),
    ):
        StripeSyncService.sync(db_session, conn)

    row = (
        db_session.query(StripeSubscription)
        .filter(StripeSubscription.connection_id == conn.id)
        .one()
    )
    # 2 * 500 + 1 * 1500
    assert row.amount_per_period == 2500


# ---------------------------------------------------------------------------
# /connections/{id}/sync-logs + read endpoints
# ---------------------------------------------------------------------------

def _auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _full_headers(tokens: dict, org_id: int) -> dict:
    return {**_auth_header(tokens), "X-Organization-Id": str(org_id)}


@pytest.fixture
def org_id(client, auth_tokens):
    me = client.get("/api/v1/auth/me", headers=_auth_header(auth_tokens)).json()
    return me["memberships"][0]["organization_id"]


def test_sync_logs_endpoint_returns_history(
    client, auth_tokens, org_id, db_session
):
    conn = _make_connection(db_session, org_id=org_id)
    # Seed two logs
    db_session.add(SyncLog(connection_id=conn.id, status=SYNC_SUCCESS, stats_json={"customers": 3}))
    db_session.add(SyncLog(connection_id=conn.id, status=SYNC_FAILED, error="boom"))
    db_session.commit()

    r = client.get(
        f"/api/v1/connections/{conn.id}/sync-logs",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    # Newest first
    assert body[0]["status"] == SYNC_FAILED
    assert body[1]["stats"] == {"customers": 3}


def test_sync_logs_cross_org_404(client, auth_tokens, org_id, db_session):
    foreign_conn = _make_connection(db_session, org_id=999)
    r = client.get(
        f"/api/v1/connections/{foreign_conn.id}/sync-logs",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.status_code == 404


def test_customers_endpoint_returns_synced_rows(
    client, auth_tokens, org_id, db_session
):
    conn = _make_connection(db_session, org_id=org_id)
    db_session.add(
        StripeCustomer(
            connection_id=conn.id,
            stripe_customer_id="cus_a",
            email="a@b.com",
            name="Alice",
            currency="usd",
            balance=0,
            delinquent=False,
            stripe_created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    r = client.get(
        f"/api/v1/connections/{conn.id}/customers",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["email"] == "a@b.com"


def test_subscriptions_endpoint_filters_by_status(
    client, auth_tokens, org_id, db_session
):
    conn = _make_connection(db_session, org_id=org_id)
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    db_session.add(
        StripeSubscription(
            connection_id=conn.id,
            stripe_subscription_id="sub_a",
            stripe_customer_id="cus_a",
            status="active",
            currency="usd",
            amount_per_period=1000,
            interval="month",
            interval_count=1,
            stripe_created_at=now,
        )
    )
    db_session.add(
        StripeSubscription(
            connection_id=conn.id,
            stripe_subscription_id="sub_b",
            stripe_customer_id="cus_b",
            status="canceled",
            currency="usd",
            amount_per_period=2000,
            interval="month",
            interval_count=1,
            stripe_created_at=now,
        )
    )
    db_session.commit()

    r = client.get(
        f"/api/v1/connections/{conn.id}/subscriptions",
        params={"status": "active"},
        headers=_full_headers(auth_tokens, org_id),
    )
    body = r.json()
    assert len(body) == 1
    assert body[0]["status"] == "active"


def test_read_endpoints_404_for_cross_org_connection(
    client, auth_tokens, org_id, db_session
):
    foreign_conn = _make_connection(db_session, org_id=999)
    for path in ("customers", "subscriptions", "charges", "sync-logs"):
        r = client.get(
            f"/api/v1/connections/{foreign_conn.id}/{path}",
            headers=_full_headers(auth_tokens, org_id),
        )
        assert r.status_code == 404, path
