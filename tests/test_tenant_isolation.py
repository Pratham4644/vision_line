from __future__ import annotations

import pytest
from starlette.testclient import TestClient


def test_org_a_cannot_access_org_b_camera(client: TestClient, admin_a_cookies: dict, viewer_a_cookies: dict):
    # cam-beta-1 belongs to org-beta
    # Org A Admin request
    resp = client.get("/api/v1/cameras/cam-beta-1", cookies=admin_a_cookies)
    assert resp.status_code == 404
    assert "not found" in resp.json()["error"]["message"].lower()

    # Org A Viewer request
    resp2 = client.get("/api/v1/cameras/cam-beta-1", cookies=viewer_a_cookies)
    assert resp2.status_code == 404


def test_org_a_cannot_access_org_b_site(client: TestClient, admin_a_cookies: dict, viewer_a_cookies: dict):
    # site-beta-1 belongs to org-beta
    resp = client.get("/api/v1/sites/site-beta-1", cookies=admin_a_cookies)
    assert resp.status_code == 404

    resp2 = client.get("/api/v1/sites/site-beta-1", cookies=viewer_a_cookies)
    assert resp2.status_code == 404


def test_org_a_cannot_create_camera_on_org_b_site(client: TestClient, admin_a_cookies: dict):
    # Attempt to attach camera to site-beta-1 belonging to Org B
    payload = {
        "site_id": "site-beta-1",
        "name": "Cross Tenant Intrusion Cam",
        "media_path": "intrusion-cam",
        "source_url": "rtsp://10.0.0.1/live",
    }
    resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 400
    assert "not found in your organization" in resp.json()["error"]["message"]


def test_org_a_cannot_create_user_in_org_b(client: TestClient, admin_a_cookies: dict):
    payload = {
        "organization_id": "org-beta",
        "email": "infiltrator@beta.com",
        "name": "Infiltrator",
        "password": "Password123!",
        "role": "ORG_ADMIN",
    }
    resp = client.post("/api/v1/users", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 201
    created_user = resp.json()["data"]

    # Even though request asked for org-beta, server-side tenant isolation MUST force org-alpha!
    assert created_user["organization_id"] == "org-alpha"
    assert created_user["organization_id"] != "org-beta"


def test_org_a_cannot_access_or_modify_org_b_user(client: TestClient, admin_a_cookies: dict):
    # user-admin-b belongs to org-beta
    get_resp = client.get("/api/v1/users/user-admin-b", cookies=admin_a_cookies)
    assert get_resp.status_code == 404

    patch_resp = client.patch(
        "/api/v1/users/user-admin-b",
        json={"name": "Hacked Name"},
        cookies=admin_a_cookies,
    )
    assert patch_resp.status_code == 404


def test_org_a_cannot_modify_or_delete_org_b_camera(client: TestClient, admin_a_cookies: dict):
    patch_resp = client.patch(
        "/api/v1/cameras/cam-beta-1",
        json={"name": "Hijacked Camera"},
        cookies=admin_a_cookies,
    )
    assert patch_resp.status_code == 404

    del_resp = client.delete("/api/v1/cameras/cam-beta-1", cookies=admin_a_cookies)
    assert del_resp.status_code == 404


def test_super_admin_can_access_cross_tenant_resources(client: TestClient, super_admin_cookies: dict):
    # SUPER_ADMIN can view cameras from both orgs
    resp_a = client.get("/api/v1/cameras/cam-alpha-1", cookies=super_admin_cookies)
    assert resp_a.status_code == 200
    assert resp_a.json()["data"]["id"] == "cam-alpha-1"

    resp_b = client.get("/api/v1/cameras/cam-beta-1", cookies=super_admin_cookies)
    assert resp_b.status_code == 200
    assert resp_b.json()["data"]["id"] == "cam-beta-1"


def test_org_a_cannot_modify_or_delete_org_b_site(client: TestClient, admin_a_cookies: dict):
    # Attempt PATCH on Site B
    patch_resp = client.patch(
        "/api/v1/sites/site-beta-1",
        json={"name": "Hijacked Site B"},
        cookies=admin_a_cookies,
    )
    assert patch_resp.status_code == 404

    # Attempt DELETE on Site B
    del_resp = client.delete("/api/v1/sites/site-beta-1", cookies=admin_a_cookies)
    assert del_resp.status_code == 404


def test_org_a_cannot_delete_org_b_user(client: TestClient, admin_a_cookies: dict):
    # Attempt DELETE or deactivation of User B
    patch_resp = client.patch(
        "/api/v1/users/user-admin-b",
        json={"is_active": False},
        cookies=admin_a_cookies,
    )
    assert patch_resp.status_code == 404


def test_malicious_client_org_id_injection_on_site_creation(client: TestClient, admin_a_cookies: dict):
    # Malicious client sends organization_id = org-beta while authenticated as org-alpha
    payload = {
        "organization_id": "org-beta",
        "name": "Injected Site",
    }
    resp = client.post("/api/v1/sites", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 201
    created_site = resp.json()["data"]
    # Backend must force organization_id to org-alpha
    assert created_site["organization_id"] == "org-alpha"
    assert created_site["organization_id"] != "org-beta"

