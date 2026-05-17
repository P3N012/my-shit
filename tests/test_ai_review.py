"""
AI weekly review tests. The Anthropic SDK is monkeypatched.
"""

from decimal import Decimal
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.core.anthropic_client import CompletionResult, TokenUsage
from app.models.ai_review import AIReview
from app.models.platform_connection import CONN_ACTIVE, PLATFORM_STRIPE, PlatformConnection
from app.models.stripe_data import StripeSubscription


def _auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _full_headers(tokens: dict, org_id: int) -> dict:
    return {**_auth_header(tokens), "X-Organization-Id": str(org_id)}


@pytest.fixture
def org_id(client, auth_tokens):
    me = client.get("/api/v1/auth/me", headers=_auth_header(auth_tokens)).json()
    return me["memberships"][0]["organization_id"]


@pytest.fixture
def seeded_org(db_session, org_id):
    """Give the org enough data for the prompt to have material to work with."""
    conn = PlatformConnection(
        organization_id=org_id,
        platform=PLATFORM_STRIPE,
        account_id="acct_review_test",
        access_token="x",
        status=CONN_ACTIVE,
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)

    now = datetime.now(timezone.utc)
    # Two active subs, one new this week.
    db_session.add(
        StripeSubscription(
            connection_id=conn.id,
            stripe_subscription_id="sub_old",
            stripe_customer_id="cus_old",
            status="active",
            currency="usd",
            amount_per_period=2900,
            interval="month",
            interval_count=1,
            started_at=now - timedelta(days=90),
            stripe_created_at=now - timedelta(days=90),
        )
    )
    db_session.add(
        StripeSubscription(
            connection_id=conn.id,
            stripe_subscription_id="sub_new",
            stripe_customer_id="cus_new",
            status="active",
            currency="usd",
            amount_per_period=29900,
            interval="month",
            interval_count=1,
            started_at=now - timedelta(days=2),
            stripe_created_at=now - timedelta(days=2),
        )
    )
    db_session.commit()
    return org_id


def _fake_completion(text: str) -> CompletionResult:
    usage = TokenUsage(input_tokens=120, output_tokens=80)
    return CompletionResult(
        text=text,
        model="claude-opus-4-7",
        stop_reason="end_turn",
        usage=usage,
        cost_usd=Decimal("0.000600"),
        raw=None,
    )


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

def test_generate_creates_review_row(client, auth_tokens, seeded_org, db_session):
    with patch(
        "app.services.ai_service.create_message",
        return_value=_fake_completion("This week MRR grew. Notable: cus_new joined."),
    ):
        r = client.post(
            "/api/v1/ai/reviews/generate",
            headers=_full_headers(auth_tokens, seeded_org),
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["model"] == "claude-opus-4-7"
    assert "MRR" in body["content"]
    assert body["metrics_snapshot"]["mrr_cents"] == 2900 + 29900

    rows = (
        db_session.query(AIReview)
        .filter(AIReview.organization_id == seeded_org)
        .all()
    )
    assert len(rows) == 1


def test_generate_includes_window_activity_in_snapshot(
    client, auth_tokens, seeded_org, db_session
):
    """The snapshot should record the new-subscriber that landed in-window."""
    with patch(
        "app.services.ai_service.create_message",
        return_value=_fake_completion("text"),
    ):
        client.post(
            "/api/v1/ai/reviews/generate",
            headers=_full_headers(auth_tokens, seeded_org),
        )

    review = db_session.query(AIReview).filter(AIReview.organization_id == seeded_org).one()
    snap = review.metrics_snapshot
    assert snap["new_customers_in_window"] == 1
    assert snap["churned_customers_in_window"] == 0
    top_new = snap["top_new_customers"]
    assert len(top_new) == 1
    assert top_new[0]["mrr_cents"] == 29900


def test_generate_503_when_ai_disabled(client, auth_tokens, seeded_org):
    from app.core import config

    original = config.settings.AI_ENABLED
    config.settings.AI_ENABLED = False
    try:
        r = client.post(
            "/api/v1/ai/reviews/generate",
            headers=_full_headers(auth_tokens, seeded_org),
        )
        assert r.status_code == 503
    finally:
        config.settings.AI_ENABLED = original


def test_generate_502_when_anthropic_fails(client, auth_tokens, seeded_org):
    with patch(
        "app.services.ai_service.create_message",
        side_effect=RuntimeError("upstream timeout"),
    ):
        r = client.post(
            "/api/v1/ai/reviews/generate",
            headers=_full_headers(auth_tokens, seeded_org),
        )
    # AIService re-raises; the route catches and turns it into 502/503.
    assert r.status_code in (502, 503)


# ---------------------------------------------------------------------------
# Latest
# ---------------------------------------------------------------------------

def test_latest_returns_null_when_no_review_yet(client, auth_tokens, org_id):
    r = client.get(
        "/api/v1/ai/reviews/latest",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.status_code == 200
    assert r.json() is None


def test_latest_returns_most_recent_review(
    client, auth_tokens, seeded_org, db_session
):
    """If we generate twice, /latest returns the second one."""
    with patch(
        "app.services.ai_service.create_message",
        return_value=_fake_completion("first review"),
    ):
        client.post(
            "/api/v1/ai/reviews/generate",
            headers=_full_headers(auth_tokens, seeded_org),
        )
    with patch(
        "app.services.ai_service.create_message",
        return_value=_fake_completion("second review"),
    ):
        client.post(
            "/api/v1/ai/reviews/generate",
            headers=_full_headers(auth_tokens, seeded_org),
        )

    r = client.get(
        "/api/v1/ai/reviews/latest",
        headers=_full_headers(auth_tokens, seeded_org),
    )
    assert r.status_code == 200
    assert r.json()["content"] == "second review"


def test_latest_is_org_scoped(client, auth_tokens, org_id, db_session):
    """A review under a different org must not leak through."""
    other = AIReview(
        organization_id=99999,
        period_start=datetime.now(timezone.utc) - timedelta(days=7),
        period_end=datetime.now(timezone.utc),
        model="claude-opus-4-7",
        content="not yours",
        metrics_snapshot={},
    )
    db_session.add(other)
    db_session.commit()

    r = client.get(
        "/api/v1/ai/reviews/latest",
        headers=_full_headers(auth_tokens, org_id),
    )
    assert r.json() is None
