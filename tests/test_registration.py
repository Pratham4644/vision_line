from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from backend.app.config import settings
from backend.app.models import UserRole


def test_customer_registration_success(client: TestClient):
    payload = {
        "name": "Alice Cooper",
        "email": "alice@customer.com",
        "password": "SecurePassword123!",
        "organization_name": "Cooper Logistics",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()["data"]

    # Verify user fields
    assert data["email"] == "alice@customer.com"
    assert data["name"] == "Alice Cooper"
    assert data["role"] == UserRole.ORG_ADMIN.value
    assert data["is_active"] is True
    assert data["organization_id"] is not None

    # Verify session cookie was set
    cookie = resp.cookies.get(settings.cookie_name)
    assert cookie is not None

    # Verify authenticated /me with that cookie works immediately
    me_resp = client.get("/api/v1/auth/me", cookies={settings.cookie_name: cookie})
    assert me_resp.status_code == 200
    assert me_resp.json()["data"]["email"] == "alice@customer.com"
    assert me_resp.json()["data"]["organization_id"] == data["organization_id"]


def test_registration_duplicate_email(client: TestClient):
    # admin@alpha.com is already seeded
    payload = {
        "name": "Impostor",
        "email": "admin@alpha.com",
        "password": "Password12345!",
        "organization_name": "New Unique Org",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409
    assert "already exists" in resp.json()["error"]["message"].lower()


def test_registration_duplicate_organization_name(client: TestClient):
    # Alpha Security Corp is already seeded
    payload = {
        "name": "New User",
        "email": "newuser@testcorp.com",
        "password": "Password12345!",
        "organization_name": "Alpha Security Corp",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409
    assert "already exists" in resp.json()["error"]["message"].lower()


def test_registration_validation_rules(client: TestClient):
    # Password too short
    resp1 = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Short Pass",
            "email": "short@test.com",
            "password": "123",
            "organization_name": "Valid Org",
        },
    )
    assert resp1.status_code == 422

    # Invalid email format
    resp2 = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Bad Email",
            "email": "not-an-email",
            "password": "Password123!",
            "organization_name": "Valid Org",
        },
    )
    assert resp2.status_code == 422

    # Empty organization name
    resp3 = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Empty Org",
            "email": "valid@test.com",
            "password": "Password123!",
            "organization_name": "   ",
        },
    )
    assert resp3.status_code == 422


def test_delete_user_success(client: TestClient, admin_a_cookies: dict):
    # Seeded user viewer-a belongs to org-alpha
    del_resp = client.delete("/api/v1/users/user-viewer-a", cookies=admin_a_cookies)
    assert del_resp.status_code == 200
    assert del_resp.json()["data"]["message"] == "User deleted successfully."

    # Verify user is gone
    get_resp = client.get("/api/v1/users/user-viewer-a", cookies=admin_a_cookies)
    assert get_resp.status_code == 404


def test_delete_user_cannot_delete_self(client: TestClient, admin_a_cookies: dict):
    # admin-a is logged in as user-admin-a
    del_resp = client.delete("/api/v1/users/user-admin-a", cookies=admin_a_cookies)
    assert del_resp.status_code == 400
    assert "cannot delete your own account" in del_resp.json()["error"]["message"].lower()


def test_delete_user_cross_tenant_isolation(client: TestClient, admin_a_cookies: dict):
    # user-viewer-b belongs to org-beta
    del_resp = client.delete("/api/v1/users/user-viewer-b", cookies=admin_a_cookies)
    assert del_resp.status_code == 404
