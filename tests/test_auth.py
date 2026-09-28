from __future__ import annotations

from datetime import datetime, timedelta, timezone
import jwt
import pytest
from starlette.testclient import TestClient

from backend.app.config import settings
from backend.app.db import db
from backend.app.models import User, UserRole


def test_login_success(client: TestClient):
    payload = {
        "email": "admin@alpha.com",
        "password": "Password123!",
    }
    resp = client.post("/api/v1/auth/login", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["email"] == "admin@alpha.com"
    assert data["data"]["role"] == "ORG_ADMIN"

    # Verify HttpOnly cookie was set
    assert settings.cookie_name in resp.cookies
    assert resp.cookies[settings.cookie_name] != ""


def test_login_invalid_password(client: TestClient):
    payload = {
        "email": "admin@alpha.com",
        "password": "WrongPassword!",
    }
    resp = client.post("/api/v1/auth/login", json=payload)
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["error"]["message"]


def test_login_unknown_email(client: TestClient):
    payload = {
        "email": "nonexistent@alpha.com",
        "password": "Password123!",
    }
    resp = client.post("/api/v1/auth/login", json=payload)
    assert resp.status_code == 401


def test_get_me_authenticated(client: TestClient, admin_a_cookies: dict):
    resp = client.get("/api/v1/auth/me", cookies=admin_a_cookies)
    assert resp.status_code == 200
    user_data = resp.json()["data"]
    assert user_data["email"] == "admin@alpha.com"
    assert user_data["organization_id"] == "org-alpha"
    assert user_data["role"] == "ORG_ADMIN"


def test_get_me_unauthenticated(client: TestClient):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_logout(client: TestClient, admin_a_cookies: dict):
    resp = client.post("/api/v1/auth/logout", cookies=admin_a_cookies)
    assert resp.status_code == 200
    cookie_val = resp.cookies.get(settings.cookie_name)
    assert cookie_val is None or cookie_val == '""' or cookie_val == ""


def test_auth_fail_closed_when_db_down(client: TestClient, admin_a_cookies: dict):
    # Simulate database outage
    db._connected = False
    try:
        resp = client.get("/api/v1/auth/me", cookies=admin_a_cookies)
        assert resp.status_code == 503
        assert "temporarily unavailable" in resp.json()["error"]["message"]
    finally:
        db._connected = True


# --- Advanced Authentication & Tampering Attack Tests ---

def test_tampered_jwt_signature(client: TestClient):
    # Create token with invalid secret key
    attacker_payload = {
        "sub": "user-admin-a",
        "email": "admin@alpha.com",
        "org": "org-alpha",
        "role": "SUPER_ADMIN",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
    }
    tampered_token = jwt.encode(attacker_payload, "completely_wrong_secret_key_attacker", algorithm="HS256")
    resp = client.get("/api/v1/auth/me", cookies={settings.cookie_name: tampered_token})
    assert resp.status_code == 401
    assert "invalid" in resp.json()["error"]["message"].lower() or "expired" in resp.json()["error"]["message"].lower()


def test_tampered_role_claim_ignored_in_favor_of_database(client: TestClient):
    # Attacker issues a token signed with the real key, claiming role=SUPER_ADMIN, but for user-viewer-a
    # The database record for user-viewer-a has role=VIEWER.
    viewer_tampered_payload = {
        "sub": "user-viewer-a",
        "email": "viewer@alpha.com",
        "org": "org-alpha",
        "role": "SUPER_ADMIN",  # Forged claim in token
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(viewer_tampered_payload, settings.jwt_secret, algorithm="HS256")

    # Attacker tries to create an organization (requires SUPER_ADMIN)
    resp = client.post("/api/v1/organizations", json={"name": "Hacked Org"}, cookies={settings.cookie_name: token})
    # Must fail because server checks DB record (VIEWER), NOT the token claim!
    assert resp.status_code == 403
    assert "access denied" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_deactivated_user_rejected(client: TestClient, admin_a_cookies: dict):
    # Deactivate admin A in database
    await db.users.update_one({"id": "user-admin-a"}, {"$set": {"is_active": False}})

    resp = client.get("/api/v1/auth/me", cookies=admin_a_cookies)
    assert resp.status_code == 403
    assert "deactivated" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_deleted_user_rejected(client: TestClient, admin_a_cookies: dict):
    # Delete user from database
    await db.users.delete_one({"id": "user-admin-a"})

    resp = client.get("/api/v1/auth/me", cookies=admin_a_cookies)
    assert resp.status_code == 401
    assert "no longer exists" in resp.json()["error"]["message"].lower()


def test_malformed_token_rejected(client: TestClient):
    resp = client.get("/api/v1/auth/me", cookies={settings.cookie_name: "not.a.valid.jwt.payload"})
    assert resp.status_code == 401


def test_expired_jwt_rejected(client: TestClient):
    # Expired token (1 hour in past)
    expired_payload = {
        "sub": "user-admin-a",
        "email": "admin@alpha.com",
        "org": "org-alpha",
        "role": "ORG_ADMIN",
        "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
    }
    expired_token = jwt.encode(expired_payload, settings.jwt_secret, algorithm="HS256")
    resp = client.get("/api/v1/auth/me", cookies={settings.cookie_name: expired_token})
    assert resp.status_code == 401
    assert "expired" in resp.json()["error"]["message"].lower() or "invalid" in resp.json()["error"]["message"].lower()


def test_tampered_org_claim_ignored_in_favor_of_database(client: TestClient):
    # Attacker issues a token claiming org=org-beta, but for user-admin-a whose DB record is org-alpha
    forged_org_payload = {
        "sub": "user-admin-a",
        "email": "admin@alpha.com",
        "org": "org-beta",  # Forged org claim in token
        "role": "ORG_ADMIN",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
    }
    token = jwt.encode(forged_org_payload, settings.jwt_secret, algorithm="HS256")

    # Attacker tries to list cameras belonging to org-beta
    resp = client.get("/api/v1/cameras", cookies={settings.cookie_name: token})
    assert resp.status_code == 200
    cameras = resp.json()["data"]
    # Returned cameras must be from org-alpha, NOT org-beta
    assert len(cameras) > 0
    for cam in cameras:
        assert cam["organization_id"] == "org-alpha"
        assert cam["organization_id"] != "org-beta"


@pytest.mark.asyncio
async def test_disabled_user_login_attempt(client: TestClient):
    # Deactivate user in database
    await db.users.update_one({"id": "user-admin-a"}, {"$set": {"is_active": False}})
    payload = {
        "email": "admin@alpha.com",
        "password": "Password123!",
    }
    resp = client.post("/api/v1/auth/login", json=payload)
    assert resp.status_code == 403
    assert "deactivated" in resp.json()["error"]["message"].lower()

