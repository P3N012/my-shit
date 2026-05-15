"""Organization endpoints and the org-scoped dependencies."""

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.models.organization import Membership
from app.utils.dependencies import get_current_membership, require_role


def _auth_header(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# ---------------------------------------------------------------------------
# /orgs endpoints
# ---------------------------------------------------------------------------

def test_register_creates_personal_org(client, auth_tokens):
    r = client.get("/api/v1/orgs", headers=_auth_header(auth_tokens))
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert len(body["organizations"]) == 1
    assert "workspace" in body["organizations"][0]["name"]


def test_list_orgs_requires_auth(client):
    r = client.get("/api/v1/orgs")
    assert r.status_code == 403  # missing bearer header


def test_create_org_makes_caller_owner(client, auth_tokens):
    r = client.post(
        "/api/v1/orgs",
        headers=_auth_header(auth_tokens),
        json={"name": "Acme Inc."},
    )
    assert r.status_code == 201
    new_org = r.json()
    assert new_org["name"] == "Acme Inc."

    me = client.get("/api/v1/auth/me", headers=_auth_header(auth_tokens)).json()
    roles = {m["organization_id"]: m["role"] for m in me["memberships"]}
    assert roles[new_org["id"]] == "owner"
    assert len(me["memberships"]) == 2  # personal org + Acme


def test_create_org_rejects_empty_name(client, auth_tokens):
    r = client.post(
        "/api/v1/orgs",
        headers=_auth_header(auth_tokens),
        json={"name": ""},
    )
    assert r.status_code == 422


def test_get_org_requires_membership(client, auth_tokens):
    # The user has org id 1 (their personal workspace).
    r = client.get("/api/v1/orgs/1", headers=_auth_header(auth_tokens))
    assert r.status_code == 200

    # Org id 999 doesn't exist / they don't belong → 403.
    r = client.get("/api/v1/orgs/999", headers=_auth_header(auth_tokens))
    assert r.status_code == 403


def test_user_cannot_see_other_users_org(client, auth_tokens):
    """Register a second user, get their org id, ensure the first user can't access it."""
    bob = client.post(
        "/api/v1/auth/register",
        json={
            "email": "bob@example.com",
            "username": "bob",
            "password": "password123",
        },
    )
    assert bob.status_code == 201

    bob_login = client.post(
        "/api/v1/auth/login",
        json={"email": "bob@example.com", "password": "password123"},
    ).json()
    bob_orgs = client.get(
        "/api/v1/orgs", headers=_auth_header(bob_login)
    ).json()
    bob_org_id = bob_orgs["organizations"][0]["id"]

    # The original (alice) user tries to read bob's org.
    r = client.get(
        f"/api/v1/orgs/{bob_org_id}", headers=_auth_header(auth_tokens)
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# get_current_membership and require_role
# ---------------------------------------------------------------------------

@pytest.fixture
def app_with_org_protected_route(client, db_session_factory):
    """
    Mount a tiny test-only route that consumes the org-scoped dependencies,
    so the deps themselves are exercised end-to-end.
    """
    from main import app

    test_router = APIRouter(prefix="/_test")

    @test_router.get("/whoami")
    def whoami(membership: Membership = Depends(get_current_membership)):
        return {
            "user_id": membership.user_id,
            "organization_id": membership.organization_id,
            "role": membership.role,
        }

    @test_router.delete(
        "/dangerous",
        dependencies=[Depends(require_role("owner"))],
    )
    def dangerous():
        return {"ok": True}

    app.include_router(test_router)
    yield client
    # Remove the test router so other tests aren't affected.
    app.router.routes = [r for r in app.router.routes if not getattr(r, "path", "").startswith("/_test")]


def test_membership_dep_requires_header(app_with_org_protected_route, auth_tokens):
    r = app_with_org_protected_route.get(
        "/_test/whoami", headers=_auth_header(auth_tokens)
    )
    assert r.status_code == 400
    assert "X-Organization-Id" in r.json()["detail"]


def test_membership_dep_rejects_foreign_org(app_with_org_protected_route, auth_tokens):
    r = app_with_org_protected_route.get(
        "/_test/whoami",
        headers={**_auth_header(auth_tokens), "X-Organization-Id": "999"},
    )
    assert r.status_code == 403


def test_membership_dep_returns_membership(app_with_org_protected_route, auth_tokens):
    me = app_with_org_protected_route.get(
        "/api/v1/auth/me", headers=_auth_header(auth_tokens)
    ).json()
    org_id = me["memberships"][0]["organization_id"]
    r = app_with_org_protected_route.get(
        "/_test/whoami",
        headers={**_auth_header(auth_tokens), "X-Organization-Id": str(org_id)},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["organization_id"] == org_id
    assert body["role"] == "owner"


def test_require_role_allows_owner(app_with_org_protected_route, auth_tokens):
    me = app_with_org_protected_route.get(
        "/api/v1/auth/me", headers=_auth_header(auth_tokens)
    ).json()
    org_id = me["memberships"][0]["organization_id"]
    r = app_with_org_protected_route.delete(
        "/_test/dangerous",
        headers={**_auth_header(auth_tokens), "X-Organization-Id": str(org_id)},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_require_role_rejects_lower_role(
    app_with_org_protected_route, auth_tokens, db_session
):
    """Demote the user to 'member' and re-check that require_role('owner') refuses."""
    me = app_with_org_protected_route.get(
        "/api/v1/auth/me", headers=_auth_header(auth_tokens)
    ).json()
    org_id = me["memberships"][0]["organization_id"]
    user_id = me["id"]

    membership = (
        db_session.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.organization_id == org_id,
        )
        .one()
    )
    membership.role = "member"
    db_session.commit()

    r = app_with_org_protected_route.delete(
        "/_test/dangerous",
        headers={**_auth_header(auth_tokens), "X-Organization-Id": str(org_id)},
    )
    assert r.status_code == 403
