def test_root_returns_welcome(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["environment"] == "test"


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}
