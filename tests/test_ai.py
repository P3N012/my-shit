"""
AI endpoint tests. The Anthropic SDK call is monkeypatched at
`app.core.anthropic_client.create_message`, so these tests don't
require an API key or network access.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.core.anthropic_client import (
    CompletionResult,
    TokenUsage,
    estimate_cost,
)
from app.models.ai_job import AIJob, JOB_QUEUED, JOB_SUCCEEDED
from app.models.ai_usage import AIUsage


def _auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _full_headers(tokens: dict, org_id: int) -> dict:
    return {**_auth_header(tokens), "X-Organization-Id": str(org_id)}


@pytest.fixture
def org_id(client, auth_tokens):
    me = client.get("/api/v1/auth/me", headers=_auth_header(auth_tokens)).json()
    return me["memberships"][0]["organization_id"]


# ---------------------------------------------------------------------------
# estimate_cost
# ---------------------------------------------------------------------------

def test_cost_is_zero_for_zero_tokens():
    assert estimate_cost("claude-opus-4-7", TokenUsage()) == Decimal("0")


def test_cost_for_opus_4_7():
    # 1M input + 1M output @ $5/$25 = $30
    cost = estimate_cost(
        "claude-opus-4-7",
        TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000),
    )
    assert cost == Decimal("30.000000")


def test_cache_read_is_cheaper_than_uncached_input():
    cached = estimate_cost(
        "claude-opus-4-7", TokenUsage(cache_read_input_tokens=1_000_000)
    )
    uncached = estimate_cost("claude-opus-4-7", TokenUsage(input_tokens=1_000_000))
    assert cached < uncached


def test_unknown_model_returns_zero():
    assert estimate_cost("not-a-real-model", TokenUsage(input_tokens=1_000_000)) == Decimal("0")


# ---------------------------------------------------------------------------
# POST /ai/messages
# ---------------------------------------------------------------------------

def _fake_completion(text="hi", usage=None) -> CompletionResult:
    usage = usage or TokenUsage(input_tokens=42, output_tokens=7)
    return CompletionResult(
        text=text,
        model="claude-opus-4-7",
        stop_reason="end_turn",
        usage=usage,
        cost_usd=estimate_cost("claude-opus-4-7", usage),
        raw=None,
    )


def test_messages_endpoint_returns_completion(client, auth_tokens, org_id, db_session):
    with patch(
        "app.services.ai_service.create_message",
        return_value=_fake_completion("hello, alice."),
    ):
        r = client.post(
            "/api/v1/ai/messages",
            headers=_full_headers(auth_tokens, org_id),
            json={"messages": [{"role": "user", "content": "hi"}]},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"] == "hello, alice."
    assert body["model"] == "claude-opus-4-7"
    assert body["usage"]["input_tokens"] == 42
    assert body["usage"]["output_tokens"] == 7
    assert Decimal(body["cost_usd"]) > 0


def test_messages_endpoint_records_usage_row(client, auth_tokens, org_id, db_session):
    fake_usage = TokenUsage(
        input_tokens=100,
        output_tokens=20,
        cache_creation_input_tokens=50,
        cache_read_input_tokens=200,
    )
    with patch(
        "app.services.ai_service.create_message",
        return_value=_fake_completion(usage=fake_usage),
    ):
        r = client.post(
            "/api/v1/ai/messages",
            headers=_full_headers(auth_tokens, org_id),
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code == 200

    rows = db_session.query(AIUsage).filter(AIUsage.organization_id == org_id).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.input_tokens == 100
    assert row.output_tokens == 20
    assert row.cache_creation_input_tokens == 50
    assert row.cache_read_input_tokens == 200
    assert row.model == "claude-opus-4-7"
    assert row.cost_usd > 0


def test_messages_endpoint_requires_org_header(client, auth_tokens):
    r = client.post(
        "/api/v1/ai/messages",
        headers=_auth_header(auth_tokens),
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 400
    assert "X-Organization-Id" in r.json()["detail"]


def test_messages_endpoint_rejects_foreign_org(client, auth_tokens):
    r = client.post(
        "/api/v1/ai/messages",
        headers={**_auth_header(auth_tokens), "X-Organization-Id": "999"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403


def test_messages_endpoint_requires_auth(client, org_id):
    r = client.post(
        "/api/v1/ai/messages",
        headers={"X-Organization-Id": str(org_id)},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 403


def test_messages_endpoint_500s_when_anthropic_fails_and_records_failure(
    client, auth_tokens, org_id, db_session
):
    with patch(
        "app.services.ai_service.create_message",
        side_effect=RuntimeError("upstream timeout"),
    ):
        r = client.post(
            "/api/v1/ai/messages",
            headers=_full_headers(auth_tokens, org_id),
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
    assert r.status_code in (502, 503)

    failures = (
        db_session.query(AIUsage)
        .filter(AIUsage.organization_id == org_id, AIUsage.error.isnot(None))
        .all()
    )
    assert len(failures) == 1
    assert "upstream timeout" in failures[0].error


def test_messages_endpoint_disabled_when_flag_off(client, auth_tokens, org_id):
    from app.core import config

    original = config.settings.AI_ENABLED
    config.settings.AI_ENABLED = False
    try:
        r = client.post(
            "/api/v1/ai/messages",
            headers=_full_headers(auth_tokens, org_id),
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 503
    finally:
        config.settings.AI_ENABLED = original


def test_messages_validates_payload(client, auth_tokens, org_id):
    r = client.post(
        "/api/v1/ai/messages",
        headers=_full_headers(auth_tokens, org_id),
        json={"messages": []},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /ai/usage
# ---------------------------------------------------------------------------

def test_usage_endpoint_starts_at_zero(client, auth_tokens, org_id):
    r = client.get("/api/v1/ai/usage", headers=_full_headers(auth_tokens, org_id))
    assert r.status_code == 200
    body = r.json()
    assert body["calls"] == 0
    assert body["input_tokens"] == 0
    assert body["cost_usd"] in ("0", "0.000000")


def test_usage_endpoint_aggregates_after_call(client, auth_tokens, org_id):
    with patch(
        "app.services.ai_service.create_message", return_value=_fake_completion()
    ):
        client.post(
            "/api/v1/ai/messages",
            headers=_full_headers(auth_tokens, org_id),
            json={"messages": [{"role": "user", "content": "a"}]},
        )
        client.post(
            "/api/v1/ai/messages",
            headers=_full_headers(auth_tokens, org_id),
            json={"messages": [{"role": "user", "content": "b"}]},
        )

    r = client.get("/api/v1/ai/usage", headers=_full_headers(auth_tokens, org_id))
    body = r.json()
    assert body["calls"] == 2
    assert body["input_tokens"] == 84  # 2 × 42
    assert body["output_tokens"] == 14
    assert Decimal(body["cost_usd"]) > 0


# ---------------------------------------------------------------------------
# Jobs — DB-level (don't try to enqueue Redis in tests; that requires a worker)
# ---------------------------------------------------------------------------

def test_job_status_endpoint_404s_for_missing(client, auth_tokens, org_id):
    r = client.get("/api/v1/ai/jobs/999", headers=_full_headers(auth_tokens, org_id))
    assert r.status_code == 404


def test_job_status_endpoint_returns_job(client, auth_tokens, org_id, db_session):
    """Seed a job directly in the DB to bypass the Redis enqueue path."""
    me = client.get("/api/v1/auth/me", headers=_auth_header(auth_tokens)).json()
    job = AIJob(
        organization_id=org_id,
        user_id=me["id"],
        kind="messages",
        status=JOB_SUCCEEDED,
        request={"messages": [{"role": "user", "content": "hi"}]},
        result={"text": "done", "model": "claude-opus-4-7"},
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    r = client.get(
        f"/api/v1/ai/jobs/{job.id}", headers=_full_headers(auth_tokens, org_id)
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == JOB_SUCCEEDED
    assert body["result"]["text"] == "done"


def test_job_status_endpoint_rejects_cross_org(client, auth_tokens, org_id, db_session):
    """A job in another org's id-space must not leak through this endpoint."""
    # Create a foreign org via a second user.
    client.post(
        "/api/v1/auth/register",
        json={"email": "bob@x.com", "username": "bob", "password": "password123"},
    )
    bob_login = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@x.com", "password": "password123"},
    ).json()
    bob_me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {bob_login['access_token']}"}
    ).json()
    bob_org_id = bob_me["memberships"][0]["organization_id"]

    foreign_job = AIJob(
        organization_id=bob_org_id,
        user_id=bob_me["id"],
        kind="messages",
        status=JOB_QUEUED,
        request={},
    )
    db_session.add(foreign_job)
    db_session.commit()
    db_session.refresh(foreign_job)

    r = client.get(
        f"/api/v1/ai/jobs/{foreign_job.id}",
        headers=_full_headers(auth_tokens, org_id),  # alice's headers
    )
    assert r.status_code == 404  # not 403 — we don't leak existence cross-org
