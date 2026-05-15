"""Meta endpoints: /, /health, /ready, plus the request-ID middleware."""

from unittest.mock import patch


def test_root_returns_welcome(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_health_is_process_only(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def test_ready_pings_database(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


def test_ready_returns_503_when_db_unreachable(client):
    """If the DB session blows up on SELECT 1, /ready must return 503."""
    from app.core.database import get_db
    from main import app

    def broken_db():
        class _Boom:
            def execute(self, *_a, **_kw):
                raise RuntimeError("connection refused")

            def close(self):
                pass

        yield _Boom()

    app.dependency_overrides[get_db] = broken_db
    try:
        r = client.get("/ready")
    finally:
        # restore the override applied by the client fixture
        pass
    assert r.status_code == 503


def test_request_id_header_is_set(client):
    r = client.get("/health")
    rid = r.headers.get("X-Request-Id")
    assert rid
    # UUID4 string length
    assert len(rid) == 36


def test_request_id_header_is_echoed_when_provided(client):
    r = client.get("/health", headers={"X-Request-Id": "my-trace-id-123"})
    assert r.headers.get("X-Request-Id") == "my-trace-id-123"
