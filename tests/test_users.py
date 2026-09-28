from __future__ import annotations

import pytest
from starlette.testclient import TestClient


def test_list_users_as_admin(client: TestClient, admin_a_cookies: dict):
    resp = client.get("/api/v1/users", cookies=admin_a_cookies)
    assert resp.status_code == 200
    users = resp.json()["data"]
    assert len(users) >= 1
    # Verify no password hashes leaked
    for u in users:
        assert "password" not in u
        assert "password_hash" not in u
        assert u["organization_id"] == "org-alpha"


def test_list_users_as_viewer_forbidden(client: TestClient, viewer_a_cookies: dict):
    resp = client.get("/api/v1/users", cookies=viewer_a_cookies)
    assert resp.status_code == 403


def test_create_user_as_admin(client: TestClient, admin_a_cookies: dict):
    payload = {
        "email": "newguard@alpha.com",
        "name": "Security Guard",
        "password": "guardpassword123",
        "role": "OPERATOR",
    }
    resp = client.post("/api/v1/users", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 201
    user = resp.json()["data"]
    assert user["email"] == "newguard@alpha.com"
    assert user["role"] == "OPERATOR"
    assert "password" not in user
    assert "password_hash" not in user


def test_create_user_duplicate_email_rejected(client: TestClient, admin_a_cookies: dict):
    payload = {
        "email": "admin@alpha.com",  # Already exists
        "name": "Duplicate",
        "password": "guardpassword123",
        "role": "VIEWER",
    }
    resp = client.post("/api/v1/users", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 409
    assert "already exists" in resp.json()["error"]["message"]


def test_toggle_user_active(client: TestClient, admin_a_cookies: dict):
    # Deactivate user-operator-a
    resp = client.patch(
        "/api/v1/users/user-operator-a",
        json={"is_active": False},
        cookies=admin_a_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False

    # Reactivate user-operator-a
    resp2 = client.patch(
        "/api/v1/users/user-operator-a",
        json={"is_active": True},
        cookies=admin_a_cookies,
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["is_active"] is True


def test_change_user_role(client: TestClient, admin_a_cookies: dict):
    resp = client.patch(
        "/api/v1/users/user-viewer-a",
        json={"role": "OPERATOR"},
        cookies=admin_a_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "OPERATOR"
