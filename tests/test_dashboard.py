"""
Dashboard aggregate tests.

Seeds a small, deterministic set of customers / subscriptions / charges
under a synthetic platform connection scoped to the test user's org,
then verifies the MRR / customer / trend / top-customer math.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.platform_connection import CONN_ACTIVE, PLATFORM_STRIPE, PlatformConnection
from app.models.stripe_data import StripeCharge, StripeCustomer, StripeSubscription
from app.services.dashboard_service import (
    DashboardService,
    normalize_to_monthly_cents,
)


def _auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _full_headers(tokens: dict, org_id: int) -> dict:
    return {**_auth_header(tokens), "X-Organization-Id": str(org_id)}


@pytest.fixture
def org_id(client, auth_tokens):
    me = client.get("/api/v1/auth/me", headers=_auth_header(auth_tokens)).json()
    return me["memberships"][0]["organization_id"]


def _make_connection(db, org_id: int) -> PlatformConnection:
    conn = PlatformConnection(
        organization_id=org_id,
        platform=PLATFORM_STRIPE,
        account_id="acct_test_dashboard",
        access_token="x",
        status=CONN_ACTIVE,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------

def test_normalize_monthly_passes_through_monthly():
    assert normalize_to_monthly_cents(2900, "month", 1) == 2900


def test_normalize_annual_divides_by_twelve():
    # $99/yr → $8.25/mo → 825 cents (int truncation)
    assert normalize_to_monthly_cents(9900, "year", 1) == 825


def test_normalize_weekly_scales_to_monthly():
    # $10/week → ~$43.33/mo
    assert normalize_to_monthly_cents(1000, "week", 1) == int(1000 * 52 / 12)


def test_normalize_interval_count_divides():
    # $99 every 3 months → $33/mo
    assert normalize_to_monthly_cents(9900, "month", 3) == 3300


def test_normalize_unknown_interval_returns_zero():
    assert normalize_to_monthly_cents(1000, None, 1) == 0
    assert normalize_to_monthly_cents(1000, "month", 0) == 0


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

def _add_active_sub(
    db, connection_id: int, customer_id: str, amount: int, *, interval: str = "month",
    interval_count: int = 1, started_days_ago: int = 60,
) -> StripeSubscription:
    started = datetime.now(timezone.utc) - timedelta(days=started_days_ago)
    sub = StripeSubscription(
        connection_id=connection_id,
        stripe_subscription_id=f"sub_{customer_id}",
        stripe_customer_id=customer_id,
        status="active",
        currency="usd",
        amount_per_period=amount,
        interval=interval,
        interval_count=interval_count,
        started_at=started,
        stripe_created_at=started,
    )
    db.add(sub)
    return sub


def _add_canceled_sub(
    db, connection_id: int, customer_id: str, amount: int, *, canceled_days_ago: int,
    started_days_ago: int = 120,
) -> StripeSubscription:
    started = datetime.now(timezone.utc) - timedelta(days=started_days_ago)
    canceled = datetime.now(timezone.utc) - timedelta(days=canceled_days_ago)
    sub = StripeSubscription(
        connection_id=connection_id,
        stripe_subscription_id=f"sub_canc_{customer_id}",
        stripe_customer_id=customer_id,
        status="canceled",
        currency="usd",
        amount_per_period=amount,
        interval="month",
        interval_count=1,
        started_at=started,
        canceled_at=canceled,
        ended_at=canceled,
        stripe_created_at=started,
    )
    db.add(sub)
    return sub


def test_overview_zero_for_org_with_no_connection(client, auth_tokens, org_id):
    r = client.get("/api/v1/dashboard/overview", headers=_full_headers(auth_tokens, org_id))
    assert r.status_code == 200
    body = r.json()
    assert body["mrr_cents"] == 0
    assert body["arr_cents"] == 0
    assert body["active_customers"] == 0
    assert body["churn_rate"] == 0


def test_overview_sums_active_subscriptions(client, auth_tokens, org_id, db_session):
    conn = _make_connection(db_session, org_id)
    _add_active_sub(db_session, conn.id, "cus_a", 2900)  # $29/mo
    _add_active_sub(db_session, conn.id, "cus_b", 9900)  # $99/mo
    _add_active_sub(db_session, conn.id, "cus_c", 99900, interval="year")  # $999/yr → ~$83/mo
    db_session.commit()

    r = client.get("/api/v1/dashboard/overview", headers=_full_headers(auth_tokens, org_id))
    body = r.json()
    # 2900 + 9900 + 8325 = 21125
    assert body["mrr_cents"] == 2900 + 9900 + 8325
    assert body["arr_cents"] == body["mrr_cents"] * 12
    assert body["active_customers"] == 3


def test_overview_ignores_canceled_subs(client, auth_tokens, org_id, db_session):
    conn = _make_connection(db_session, org_id)
    _add_active_sub(db_session, conn.id, "cus_a", 2900)
    _add_canceled_sub(db_session, conn.id, "cus_b", 9900, canceled_days_ago=10)
    db_session.commit()

    r = client.get("/api/v1/dashboard/overview", headers=_full_headers(auth_tokens, org_id))
    body = r.json()
    assert body["mrr_cents"] == 2900
    assert body["active_customers"] == 1


def test_overview_computes_churn_rate(client, auth_tokens, org_id, db_session):
    conn = _make_connection(db_session, org_id)
    # 4 subs active at "30 days ago" — three still active, one canceled in window
    for i in range(3):
        _add_active_sub(db_session, conn.id, f"cus_{i}", 2900, started_days_ago=90)
    _add_canceled_sub(
        db_session, conn.id, "cus_churned", 2900,
        started_days_ago=90, canceled_days_ago=10,
    )
    db_session.commit()

    r = client.get("/api/v1/dashboard/overview", headers=_full_headers(auth_tokens, org_id))
    body = r.json()
    # 1 churned out of 4 active at start of window = 0.25
    assert body["churn_rate"] == pytest.approx(0.25, abs=0.001)


def test_overview_isolates_orgs(client, auth_tokens, org_id, db_session):
    """A foreign org's subs must NOT appear in this org's MRR."""
    foreign_conn = _make_connection(db_session, org_id=99999)
    _add_active_sub(db_session, foreign_conn.id, "cus_foreign", 50000)
    db_session.commit()

    r = client.get("/api/v1/dashboard/overview", headers=_full_headers(auth_tokens, org_id))
    body = r.json()
    assert body["mrr_cents"] == 0
    assert body["active_customers"] == 0


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

def test_trends_returns_requested_number_of_points(client, auth_tokens, org_id, db_session):
    conn = _make_connection(db_session, org_id)
    _add_active_sub(db_session, conn.id, "cus_a", 2900, started_days_ago=200)
    db_session.commit()

    r = client.get(
        "/api/v1/dashboard/trends?months=6",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) == 6
    # Newest point should reflect the active sub.
    assert body["points"][-1]["mrr_cents"] == 2900


def test_trends_shows_growth_over_time(client, auth_tokens, org_id, db_session):
    """A second sub starting mid-trend should bump later points."""
    conn = _make_connection(db_session, org_id)
    _add_active_sub(db_session, conn.id, "cus_old", 2900, started_days_ago=300)
    _add_active_sub(db_session, conn.id, "cus_new", 9900, started_days_ago=30)
    db_session.commit()

    r = client.get(
        "/api/v1/dashboard/trends?months=12",
        headers=_full_headers(auth_tokens, org_id),
    )
    points = r.json()["points"]
    assert points[0]["mrr_cents"] < points[-1]["mrr_cents"], "MRR should rise across the period"


# ---------------------------------------------------------------------------
# Top customers
# ---------------------------------------------------------------------------

def test_top_customers_orders_by_revenue(client, auth_tokens, org_id, db_session):
    conn = _make_connection(db_session, org_id)
    now = datetime.now(timezone.utc)

    # Two customers with very different spend in the last 90 days
    for cid, amount, count in [("cus_big", 9900, 3), ("cus_small", 2900, 1)]:
        db_session.add(
            StripeCustomer(
                connection_id=conn.id,
                stripe_customer_id=cid,
                name=f"{cid.title()} Co",
                email=f"{cid}@example.com",
                currency="usd",
                stripe_created_at=now - timedelta(days=200),
            )
        )
        for i in range(count):
            db_session.add(
                StripeCharge(
                    connection_id=conn.id,
                    stripe_charge_id=f"ch_{cid}_{i}",
                    stripe_customer_id=cid,
                    amount=amount,
                    amount_refunded=0,
                    currency="usd",
                    status="succeeded",
                    paid=True,
                    refunded=False,
                    livemode=False,
                    stripe_created_at=now - timedelta(days=i * 10),
                )
            )
    db_session.commit()

    r = client.get(
        "/api/v1/dashboard/top-customers?limit=5",
        headers=_full_headers(auth_tokens, org_id),
    )
    body = r.json()
    assert [c["stripe_customer_id"] for c in body["customers"]] == ["cus_big", "cus_small"]
    assert body["customers"][0]["total_revenue_cents"] == 9900 * 3
    assert body["customers"][0]["name"] == "Cus_Big Co"


def test_top_customers_ignores_failed_charges(client, auth_tokens, org_id, db_session):
    conn = _make_connection(db_session, org_id)
    now = datetime.now(timezone.utc)
    db_session.add(
        StripeCustomer(
            connection_id=conn.id,
            stripe_customer_id="cus_a",
            currency="usd",
            stripe_created_at=now - timedelta(days=200),
        )
    )
    db_session.add(
        StripeCharge(
            connection_id=conn.id,
            stripe_charge_id="ch_failed",
            stripe_customer_id="cus_a",
            amount=99900,
            currency="usd",
            status="failed",
            paid=False,
            stripe_created_at=now - timedelta(days=10),
        )
    )
    db_session.commit()

    r = client.get(
        "/api/v1/dashboard/top-customers",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.json()["customers"] == []


# ---------------------------------------------------------------------------
# Auth + org-scoping on every endpoint
# ---------------------------------------------------------------------------

def test_dashboard_routes_require_org_header(client, auth_tokens):
    for path in ("overview", "trends", "top-customers", "movements", "activity"):
        r = client.get(
            f"/api/v1/dashboard/{path}", headers=_auth_header(auth_tokens)
        )
        assert r.status_code == 400, path


def test_dashboard_routes_reject_foreign_org(client, auth_tokens):
    for path in ("overview", "trends", "top-customers", "movements", "activity"):
        r = client.get(
            f"/api/v1/dashboard/{path}",
            headers={**_auth_header(auth_tokens), "X-Organization-Id": "999"},
        )
        assert r.status_code == 403, path


# ---------------------------------------------------------------------------
# Failed payments (lives on /overview)
# ---------------------------------------------------------------------------

def test_overview_counts_failed_payments_in_window(client, auth_tokens, org_id, db_session):
    conn = _make_connection(db_session, org_id)
    now = datetime.now(timezone.utc)

    # Two failed charges in window, one succeeded (ignored), one failed but old (ignored).
    db_session.add_all([
        StripeCharge(
            connection_id=conn.id,
            stripe_charge_id="ch_failed_1",
            amount=9900,
            currency="usd",
            status="failed",
            paid=False,
            stripe_created_at=now - timedelta(days=2),
        ),
        StripeCharge(
            connection_id=conn.id,
            stripe_charge_id="ch_failed_2",
            amount=2900,
            currency="usd",
            status="failed",
            paid=False,
            stripe_created_at=now - timedelta(days=10),
        ),
        StripeCharge(
            connection_id=conn.id,
            stripe_charge_id="ch_success",
            amount=99900,
            currency="usd",
            status="succeeded",
            paid=True,
            stripe_created_at=now - timedelta(days=5),
        ),
        StripeCharge(
            connection_id=conn.id,
            stripe_charge_id="ch_failed_old",
            amount=99900,
            currency="usd",
            status="failed",
            paid=False,
            stripe_created_at=now - timedelta(days=60),
        ),
    ])
    db_session.commit()

    r = client.get("/api/v1/dashboard/overview", headers=_full_headers(auth_tokens, org_id))
    body = r.json()
    assert body["failed_payments_count"] == 2
    assert body["failed_payments_cents"] == 9900 + 2900


# ---------------------------------------------------------------------------
# MRR movements
# ---------------------------------------------------------------------------

def test_movements_records_new_and_churn(client, auth_tokens, org_id, db_session):
    conn = _make_connection(db_session, org_id)
    now = datetime.now(timezone.utc)
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Sub created this month (counts as new this month)
    _add_active_sub(
        db_session, conn.id, "cus_new", 2900, started_days_ago=2,
    )
    # Sub canceled this month (counts as churn this month). started_at way back.
    canceled_at = now - timedelta(days=3)
    db_session.add(StripeSubscription(
        connection_id=conn.id,
        stripe_subscription_id="sub_canc",
        stripe_customer_id="cus_canc",
        status="canceled",
        currency="usd",
        amount_per_period=9900,
        interval="month",
        interval_count=1,
        started_at=now - timedelta(days=300),
        canceled_at=canceled_at,
        ended_at=canceled_at,
        stripe_created_at=now - timedelta(days=300),
    ))
    db_session.commit()

    r = client.get(
        "/api/v1/dashboard/movements?months=12",
        headers=_full_headers(auth_tokens, org_id),
    )
    body = r.json()
    assert len(body["points"]) == 12
    # The last point (current month) holds both
    last = body["points"][-1]
    assert last["new_mrr_cents"] == 2900
    assert last["churn_mrr_cents"] == 9900


def test_movements_is_empty_without_connection(client, auth_tokens, org_id):
    r = client.get(
        "/api/v1/dashboard/movements", headers=_full_headers(auth_tokens, org_id)
    )
    assert r.json()["points"] == []


# ---------------------------------------------------------------------------
# Activity feed
# ---------------------------------------------------------------------------

def test_activity_feed_orders_newest_first(client, auth_tokens, org_id, db_session):
    conn = _make_connection(db_session, org_id)
    now = datetime.now(timezone.utc)

    # Seed one of each kind, with distinct timestamps so order is stable.
    db_session.add(StripeCustomer(
        connection_id=conn.id,
        stripe_customer_id="cus_a",
        name="Acme Labs",
        currency="usd",
        stripe_created_at=now - timedelta(days=10),
    ))
    db_session.add(StripeSubscription(
        connection_id=conn.id,
        stripe_subscription_id="sub_new",
        stripe_customer_id="cus_a",
        status="active",
        currency="usd",
        amount_per_period=9900,
        interval="month",
        interval_count=1,
        started_at=now - timedelta(days=5),
        stripe_metadata={"plan": "Pro"},
        stripe_created_at=now - timedelta(days=5),
    ))
    db_session.add(StripeCharge(
        connection_id=conn.id,
        stripe_charge_id="ch_fail",
        stripe_customer_id="cus_a",
        amount=9900,
        currency="usd",
        status="failed",
        paid=False,
        stripe_created_at=now - timedelta(hours=2),
        failure_message="Your card was declined.",
    ))
    db_session.commit()

    r = client.get(
        "/api/v1/dashboard/activity",
        headers=_full_headers(auth_tokens, org_id),
    )
    events = r.json()["events"]
    assert len(events) == 2
    assert events[0]["kind"] == "charge_failed"             # most recent first
    assert events[0]["description"] == "Your card was declined."
    assert events[1]["kind"] == "subscription_started"
    assert events[1]["description"] == "Subscribed to Pro"
    # Both events resolved the customer name
    assert all(e["customer_name"] == "Acme Labs" for e in events)


def test_activity_feed_skips_events_outside_window(client, auth_tokens, org_id, db_session):
    conn = _make_connection(db_session, org_id)
    now = datetime.now(timezone.utc)
    # 90 days ago — outside the default 30-day window
    db_session.add(StripeSubscription(
        connection_id=conn.id,
        stripe_subscription_id="sub_old",
        stripe_customer_id="cus_x",
        status="active",
        currency="usd",
        amount_per_period=2900,
        interval="month",
        interval_count=1,
        started_at=now - timedelta(days=90),
        stripe_created_at=now - timedelta(days=90),
    ))
    db_session.commit()

    r = client.get(
        "/api/v1/dashboard/activity?days=30",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.json()["events"] == []


# ---------------------------------------------------------------------------
# Customer detail
# ---------------------------------------------------------------------------

def test_customer_detail_returns_full_record(client, auth_tokens, org_id, db_session):
    conn = _make_connection(db_session, org_id)
    now = datetime.now(timezone.utc)

    db_session.add(StripeCustomer(
        connection_id=conn.id,
        stripe_customer_id="cus_detail",
        name="Detail Co",
        email="ops@detail.test",
        currency="usd",
        delinquent=False,
        stripe_created_at=now - timedelta(days=120),
    ))
    db_session.add(StripeSubscription(
        connection_id=conn.id,
        stripe_subscription_id="sub_d",
        stripe_customer_id="cus_detail",
        status="active",
        currency="usd",
        amount_per_period=9900,
        interval="month",
        interval_count=1,
        started_at=now - timedelta(days=120),
        stripe_created_at=now - timedelta(days=120),
    ))
    # Two succeeded charges + one failed (failed excluded from LTV).
    for i, (amt, status) in enumerate([(9900, "succeeded"), (9900, "succeeded"), (9900, "failed")]):
        db_session.add(StripeCharge(
            connection_id=conn.id,
            stripe_charge_id=f"ch_d_{i}",
            stripe_customer_id="cus_detail",
            amount=amt,
            currency="usd",
            status=status,
            paid=status == "succeeded",
            stripe_created_at=now - timedelta(days=i * 30),
        ))
    db_session.commit()

    r = client.get(
        "/api/v1/dashboard/customers/cus_detail",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Detail Co"
    assert body["current_mrr_cents"] == 9900
    assert body["lifetime_value_cents"] == 9900 * 2  # failed charge excluded
    assert len(body["subscriptions"]) == 1
    assert len(body["charges"]) == 3


def test_customer_detail_404_for_unknown(client, auth_tokens, org_id):
    r = client.get(
        "/api/v1/dashboard/customers/cus_nope",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.status_code == 404


def test_customer_detail_404_cross_org(client, auth_tokens, org_id, db_session):
    foreign = _make_connection(db_session, org_id=99999)
    db_session.add(StripeCustomer(
        connection_id=foreign.id,
        stripe_customer_id="cus_foreign",
        name="Foreign Co",
        currency="usd",
        stripe_created_at=datetime.now(timezone.utc),
    ))
    db_session.commit()

    r = client.get(
        "/api/v1/dashboard/customers/cus_foreign",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.status_code == 404
