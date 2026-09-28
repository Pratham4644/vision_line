from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from backend.app.models import UserRole
from backend.app.permissions import can_manage_role, has_permission


def test_permission_matrix():
    # SUPER_ADMIN has platform management
    assert has_permission(UserRole.SUPER_ADMIN, "org:create")
    assert has_permission(UserRole.SUPER_ADMIN, "camera:delete")

    # ORG_ADMIN has org management but not global org creation
    assert not has_permission(UserRole.ORG_ADMIN, "org:create")
    assert has_permission(UserRole.ORG_ADMIN, "camera:create")
    assert has_permission(UserRole.ORG_ADMIN, "site:create")
    assert has_permission(UserRole.ORG_ADMIN, "user:create")

    # OPERATOR can view and control operational stream state but not create resources
    assert not has_permission(UserRole.OPERATOR, "camera:create")
    assert not has_permission(UserRole.OPERATOR, "site:create")
    assert not has_permission(UserRole.OPERATOR, "user:create")
    assert has_permission(UserRole.OPERATOR, "camera:read")
    assert has_permission(UserRole.OPERATOR, "camera:update")

    # VIEWER is strictly read-only
    assert not has_permission(UserRole.VIEWER, "camera:create")
    assert not has_permission(UserRole.VIEWER, "camera:update")
    assert not has_permission(UserRole.VIEWER, "camera:delete")
    assert has_permission(UserRole.VIEWER, "camera:read")


def test_role_hierarchy_management():
    # SUPER_ADMIN can create any role
    assert can_manage_role(UserRole.SUPER_ADMIN, UserRole.SUPER_ADMIN)
    assert can_manage_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)

    # ORG_ADMIN CANNOT create SUPER_ADMIN
    assert not can_manage_role(UserRole.ORG_ADMIN, UserRole.SUPER_ADMIN)
    assert can_manage_role(UserRole.ORG_ADMIN, UserRole.ORG_ADMIN)
    assert can_manage_role(UserRole.ORG_ADMIN, UserRole.OPERATOR)
    assert can_manage_role(UserRole.ORG_ADMIN, UserRole.VIEWER)

    # OPERATOR and VIEWER cannot manage roles
    assert not can_manage_role(UserRole.OPERATOR, UserRole.VIEWER)
    assert not can_manage_role(UserRole.VIEWER, UserRole.VIEWER)


def test_org_admin_cannot_create_super_admin(client: TestClient, admin_a_cookies: dict):
    payload = {
        "email": "hacked_super@alpha.com",
        "name": "Malicious Admin",
        "password": "Password123!",
        "role": "SUPER_ADMIN",
    }
    resp = client.post("/api/v1/users", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 403
    assert "permission to assign the role 'SUPER_ADMIN'" in resp.json()["error"]["message"]


def test_viewer_cannot_create_site_or_camera(client: TestClient, viewer_a_cookies: dict):
    # Try creating site as VIEWER
    site_payload = {"name": "Unauthorized Site"}
    resp = client.post("/api/v1/sites", json=site_payload, cookies=viewer_a_cookies)
    assert resp.status_code == 403

    # Try creating camera as VIEWER
    cam_payload = {
        "site_id": "site-alpha-1",
        "name": "Unauthorized Cam",
        "media_path": "unauthorized-cam",
        "source_url": "rtsp://192.168.1.1/live",
    }
    resp = client.post("/api/v1/cameras", json=cam_payload, cookies=viewer_a_cookies)
    assert resp.status_code == 403


def test_org_admin_rbac_boundaries(client: TestClient, admin_a_cookies: dict):
    # ORG_ADMIN cannot create organization (SUPER_ADMIN only)
    org_payload = {"name": "Malicious New Org"}
    resp = client.post("/api/v1/organizations", json=org_payload, cookies=admin_a_cookies)
    assert resp.status_code == 403

    # ORG_ADMIN cannot modify another organization (returns 404 to prevent org enumeration)
    patch_resp = client.patch(
        "/api/v1/organizations/org-beta",
        json={"name": "Hacked Org Beta"},
        cookies=admin_a_cookies,
    )
    assert patch_resp.status_code in (403, 404)


def test_operator_rbac_boundaries(client: TestClient, operator_a_cookies: dict):
    # OPERATOR cannot manage users
    user_payload = {
        "email": "operator_created@alpha.com",
        "name": "Operator New User",
        "password": "Password123!",
        "role": "VIEWER",
    }
    resp = client.post("/api/v1/users", json=user_payload, cookies=operator_a_cookies)
    assert resp.status_code == 403

    # OPERATOR cannot modify organization
    resp_org = client.patch(
        "/api/v1/organizations/org-alpha",
        json={"name": "Operator Renamed Org"},
        cookies=operator_a_cookies,
    )
    assert resp_org.status_code == 403

    # OPERATOR cannot create cameras
    cam_payload = {
        "site_id": "site-alpha-1",
        "name": "Operator Cam",
        "media_path": "operator-cam",
        "source_url": "rtsp://192.168.1.10/live",
    }
    resp_cam = client.post("/api/v1/cameras", json=cam_payload, cookies=operator_a_cookies)
    assert resp_cam.status_code == 403


def test_viewer_rbac_boundaries(client: TestClient, viewer_a_cookies: dict):
    # VIEWER cannot delete camera
    del_cam = client.delete("/api/v1/cameras/cam-alpha-1", cookies=viewer_a_cookies)
    assert del_cam.status_code == 403

    # VIEWER cannot modify site
    patch_site = client.patch(
        "/api/v1/sites/site-alpha-1",
        json={"name": "Viewer Renamed Site"},
        cookies=viewer_a_cookies,
    )
    assert patch_site.status_code == 403

    # VIEWER cannot manage users
    user_payload = {
        "email": "viewer_created@alpha.com",
        "name": "Viewer New User",
        "password": "Password123!",
        "role": "VIEWER",
    }
    resp_user = client.post("/api/v1/users", json=user_payload, cookies=viewer_a_cookies)
    assert resp_user.status_code == 403

