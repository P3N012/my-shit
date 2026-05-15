"""Shared test fixtures.

Each test gets its own SQLite database (per `tmp_path`) so tests don't
share state. The app's `get_db` dependency is overridden to use that
database via FastAPI's `dependency_overrides`.
"""

import os

# Settings is constructed at import time. Make sure required env vars exist
# before `app.core.config` is imported anywhere.
os.environ.setdefault("DATABASE_URL", "sqlite:///./pytest_placeholder.db")
os.environ.setdefault("ACCESS_TOKEN_SECRET", "test-access-secret")
os.environ.setdefault("REFRESH_TOKEN_SECRET", "test-refresh-secret")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
)
# Rate limits stay on by default in production; disable globally for tests
# unless a specific test re-enables them.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import database
import app.models  # noqa: F401 — register models with Base.metadata


@pytest.fixture
def test_db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    database.Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session_factory(test_db_engine):
    return sessionmaker(bind=test_db_engine, autocommit=False, autoflush=False)


@pytest.fixture
def db_session(db_session_factory):
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session_factory):
    from main import app
    from app.core.database import get_db

    def override_get_db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user(client):
    """A registered user with credentials returned for follow-up logins."""
    payload = {
        "email": "alice@example.com",
        "username": "alice",
        "password": "password123",
    }
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return payload


@pytest.fixture
def auth_tokens(client, registered_user):
    """Logged-in user — returns the initial access + refresh pair."""
    r = client.post(
        "/api/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert r.status_code == 200, r.text
    return r.json()
