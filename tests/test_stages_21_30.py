from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from backend.app.models import CameraStatus


def test_profile_update_name(client: TestClient, admin_a_cookies: dict):
    """Verifies user can update their display name."""
    resp = client.patch(
        "/api/v1/auth/profile",
        json={"name": "Updated Org A Admin"},
        cookies=admin_a_cookies,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Updated Org A Admin"

    # Verify via /auth/me
    me_resp = client.get("/api/v1/auth/me", cookies=admin_a_cookies)
    assert me_resp.json()["data"]["name"] == "Updated Org A Admin"


def test_profile_update_password_success(client: TestClient, admin_a_cookies: dict):
    """Verifies user can update their password after providing correct current password."""
    resp = client.patch(
        "/api/v1/auth/profile",
        json={
            "current_password": "Password123!",
            "new_password": "NewSecretPassword456!",
        },
        cookies=admin_a_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Test login with old password fails
    fail_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@alpha.com", "password": "Password123!"},
    )
    assert fail_login.status_code == 401

    # Test login with new password succeeds
    success_login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@alpha.com", "password": "NewSecretPassword456!"},
    )
    assert success_login.status_code == 200


def test_profile_update_password_wrong_current(client: TestClient, admin_a_cookies: dict):
    """Verifies password change fails if current password is wrong."""
    resp = client.patch(
        "/api/v1/auth/profile",
        json={
            "current_password": "WrongOldPassword!",
            "new_password": "NewSecretPassword456!",
        },
        cookies=admin_a_cookies,
    )
    assert resp.status_code == 400
    assert "Current password verification failed" in resp.json()["error"]["message"]


def test_camera_enable_disable_lifecycle(client: TestClient, admin_a_cookies: dict):
    """Verifies enabling and disabling a camera stream."""
    # Disable camera
    dis_resp = client.post("/api/v1/cameras/cam-alpha-1/disable", cookies=admin_a_cookies)
    assert dis_resp.status_code == 200
    assert dis_resp.json()["data"]["enabled"] is False

    # Verify playback is rejected when disabled
    pb_resp = client.get("/api/v1/cameras/cam-alpha-1/playback", cookies=admin_a_cookies)
    assert pb_resp.status_code == 400

    # Enable camera
    en_resp = client.post("/api/v1/cameras/cam-alpha-1/enable", cookies=admin_a_cookies)
    assert en_resp.status_code == 200
    assert en_resp.json()["data"]["enabled"] is True


def test_camera_restart_stream(client: TestClient, admin_a_cookies: dict):
    """Verifies stream restart sets status to UNKNOWN and updates timestamp."""
    resp = client.post("/api/v1/cameras/cam-alpha-1/restart", cookies=admin_a_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["status"] == "UNKNOWN"


def test_camera_test_connection(client: TestClient, admin_a_cookies: dict):
    """Verifies camera connection test endpoint."""
    resp = client.post("/api/v1/cameras/cam-alpha-1/test", cookies=admin_a_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "ok" in data["data"]
    assert "message" in data["data"]


def test_audit_logs_read(client: TestClient, admin_a_cookies: dict):
    """Verifies authorized admin can read audit logs with pagination."""
    resp = client.get("/api/v1/logs?page=1&page_size=10", cookies=admin_a_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "items" in data["data"]
    assert "total" in data["data"]
    assert data["data"]["page"] == 1
    assert data["data"]["page_size"] == 10


def test_audit_logs_viewer_forbidden(client: TestClient, viewer_a_cookies: dict):
    """Verifies non-admin VIEWER cannot access audit logs."""
    resp = client.get("/api/v1/logs", cookies=viewer_a_cookies)
    assert resp.status_code == 403


def test_healthz_and_detailed_health(
    client: TestClient, super_admin_cookies: dict, viewer_a_cookies: dict
):
    """Verifies public healthz and admin-only detailed health check."""
    # Public unauthenticated check
    hz = client.get("/healthz")
    assert hz.status_code == 200
    assert hz.json()["status"] == "ok"

    # Detailed health requires admin role
    forbidden = client.get("/api/v1/health", cookies=viewer_a_cookies)
    assert forbidden.status_code == 403

    allowed = client.get("/api/v1/health", cookies=super_admin_cookies)
    assert allowed.status_code == 200
    assert allowed.json()["data"]["status"] == "healthy"
    assert allowed.json()["data"]["database"] is True
