"""Rate limiting is disabled globally in tests (see conftest); this module
flips it back on and verifies the limit fires."""

import pytest

from app.core.limiter import limiter


@pytest.fixture
def rate_limits_on():
    limiter.enabled = True
    # slowapi keeps in-memory counters; reset so other tests' calls don't
    # count toward this test's quota.
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()


def test_login_endpoint_is_rate_limited(client, rate_limits_on, registered_user):
    """RATE_LIMIT_LOGIN defaults to 5/minute. The 6th call must 429."""
    body = {
        "email": registered_user["email"],
        "password": registered_user["password"],
    }
    statuses = [
        client.post("/api/v1/auth/login", json=body).status_code
        for _ in range(6)
    ]
    # First 5 succeed; 6th is throttled.
    assert statuses.count(200) == 5
    assert statuses[-1] == 429
    body = client.post("/api/v1/auth/login", json=body).json()
    assert "Rate limit" in body["detail"]
