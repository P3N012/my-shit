"""CORS allowlist behavior."""


def _preflight(client, origin: str):
    return client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )


def test_allowlisted_origin_is_echoed(client):
    r = _preflight(client, "http://localhost:3000")
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_second_allowlisted_origin_is_echoed(client):
    r = _preflight(client, "http://localhost:5173")
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_unknown_origin_is_rejected(client):
    r = _preflight(client, "http://evil.example.com")
    assert r.headers.get("access-control-allow-origin") is None
