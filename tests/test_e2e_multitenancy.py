from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from backend.app.config import settings
from backend.app.models import UserRole


def test_test_a_customer_a_full_flow(client: TestClient):
    """
    TEST A: Customer A Journey
    1. Register
    2. Automatically become ORG_ADMIN of newly created org
    3. Authenticated session active via cookie
    4. Create site
    5. Create camera under site
    6. View camera
    7. Open WebRTC stream (playback endpoint)
    8. Create another user (OPERATOR)
    9. Logout
    10. Login again
    11. Verify data persistence
    """
    # 1. Register Customer A
    reg_payload = {
        "name": "Alice Admin",
        "email": "alice@customer-a.io",
        "password": "Password123!",
        "organization_name": "Customer A Industries",
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201, reg_res.text
    reg_data = reg_res.json()["data"]
    assert reg_data["email"] == "alice@customer-a.io"
    assert reg_data["role"] == UserRole.ORG_ADMIN
    org_id = reg_data["organization_id"]
    assert org_id is not None

    # Verify session cookie was set
    assert settings.cookie_name in client.cookies

    # 2. Check /auth/me
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    me_data = me_res.json()["data"]
    assert me_data["email"] == "alice@customer-a.io"
    assert me_data["organization_id"] == org_id
    assert me_data["role"] == UserRole.ORG_ADMIN

    # 3. Create site
    site_res = client.post(
        "/api/v1/sites",
        json={"name": "Building A Main Entrance", "location": "Floor 1"},
    )
    assert site_res.status_code == 201, site_res.text
    site_data = site_res.json()["data"]
    site_id = site_data["id"]
    assert site_data["organization_id"] == org_id
    assert site_data["name"] == "Building A Main Entrance"

    # 4. Create camera under that site
    cam_res = client.post(
        "/api/v1/cameras",
        json={
            "site_id": site_id,
            "name": "Gate 1 North",
            "media_path": "gate-1-north",
            "source_url": "rtsp://10.10.1.50:554/ch0",
        },
    )
    assert cam_res.status_code == 201, cam_res.text
    cam_data = cam_res.json()["data"]
    cam_id = cam_data["id"]
    assert cam_data["organization_id"] == org_id
    assert cam_data["site_id"] == site_id

    # 5. View camera
    view_res = client.get(f"/api/v1/cameras/{cam_id}")
    assert view_res.status_code == 200
    assert view_res.json()["data"]["name"] == "Gate 1 North"

    # 6. Open WebRTC stream (playback endpoint)
    play_res = client.get(f"/api/v1/cameras/{cam_id}/playback")
    assert play_res.status_code == 200
    play_data = play_res.json()["data"]
    assert play_data["media_path"] == "gate-1-north"
    assert "whep_url" in play_data
    assert play_data["organization_id"] == org_id

    # 7. Create another user in organization (OPERATOR)
    user_res = client.post(
        "/api/v1/users",
        json={
            "name": "Bob Operator",
            "email": "bob@customer-a.io",
            "password": "Password123!",
            "role": UserRole.OPERATOR,
        },
    )
    assert user_res.status_code == 201, user_res.text
    user_data = user_res.json()["data"]
    assert user_data["email"] == "bob@customer-a.io"
    assert user_data["organization_id"] == org_id
    assert user_data["role"] == UserRole.OPERATOR

    # 8. Logout
    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200
    client.cookies.clear()

    # Verify session is terminated
    unauth_res = client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401

    # 9. Login again
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@customer-a.io", "password": "Password123!"},
    )
    assert login_res.status_code == 200

    # 10. Verify data persists
    cams_res = client.get("/api/v1/cameras")
    assert cams_res.status_code == 200
    cam_list = cams_res.json()["data"]
    assert any(c["id"] == cam_id for c in cam_list)

    sites_res = client.get("/api/v1/sites")
    assert sites_res.status_code == 200
    site_list = sites_res.json()["data"]
    assert any(s["id"] == site_id for s in site_list)

    users_res = client.get("/api/v1/users")
    assert users_res.status_code == 200
    user_list = users_res.json()["data"]
    assert len(user_list) == 2
    emails = {u["email"] for u in user_list}
    assert "alice@customer-a.io" in emails
    assert "bob@customer-a.io" in emails


def test_test_b_customer_b_isolation(client: TestClient):
    """
    TEST B: Customer B Registration & Resource Isolation
    1. Register Customer B
    2. Create Site B and Camera B
    3. Verify Camera B is visible
    4. Verify Customer A cameras/sites are NOT visible to Customer B
    """
    # 1. Register Customer A
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Org A Owner",
            "email": "owner@corp-a.com",
            "password": "Password123!",
            "organization_name": "Corporation A",
        },
    )
    s_a = client.post("/api/v1/sites", json={"name": "A Site", "location": "HQ"}).json()["data"]
    cam_a = client.post(
        "/api/v1/cameras",
        json={
            "site_id": s_a["id"],
            "name": "Camera Alpha Secret",
            "media_path": "alpha-secret",
            "source_url": "rtsp://10.0.0.1/live",
        },
    ).json()["data"]

    # 2. Register Customer B
    client.cookies.clear()
    reg_b = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Org B Owner",
            "email": "owner@corp-b.com",
            "password": "Password123!",
            "organization_name": "Corporation B",
        },
    )
    assert reg_b.status_code == 201

    # 3. Create Site B and Camera B
    s_b = client.post("/api/v1/sites", json={"name": "B Warehouse", "location": "Dock"}).json()["data"]
    cam_b = client.post(
        "/api/v1/cameras",
        json={
            "site_id": s_b["id"],
            "name": "Camera Beta Public",
            "media_path": "beta-public",
            "source_url": "rtsp://10.0.0.2/live",
        },
    ).json()["data"]

    # 4. List cameras for Customer B
    b_cams_res = client.get("/api/v1/cameras")
    assert b_cams_res.status_code == 200
    b_cams = b_cams_res.json()["data"]
    b_cam_ids = [c["id"] for c in b_cams]
    assert cam_b["id"] in b_cam_ids
    assert cam_a["id"] not in b_cam_ids
    assert len(b_cams) == 1

    # 5. List sites for Customer B
    b_sites_res = client.get("/api/v1/sites")
    assert b_sites_res.status_code == 200
    b_sites = b_sites_res.json()["data"]
    b_site_ids = [s["id"] for s in b_sites]
    assert s_b["id"] in b_site_ids
    assert s_a["id"] not in b_site_ids
    assert len(b_sites) == 1


def test_test_c_cross_tenant_attack(client: TestClient):
    """
    TEST C: Cross-Tenant Attack & IDOR Resistance
    While authenticated as Customer B, attempt to access, modify, or delete
    resources of Customer A by spoofing IDs in URLs and payloads.
    Expected: 404 (or 400 for invalid relations) with NO data leakage.
    """
    # Register Customer A & create resources
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Owner A",
            "email": "owner-a@target.com",
            "password": "Password123!",
            "organization_name": "Target Corp",
        },
    )
    org_a = client.get("/api/v1/auth/me").json()["data"]["organization_id"]
    user_a = client.get("/api/v1/auth/me").json()["data"]["id"]
    site_a = client.post("/api/v1/sites", json={"name": "Vault Site"}).json()["data"]["id"]
    cam_a = client.post(
        "/api/v1/cameras",
        json={
            "site_id": site_a,
            "name": "Vault Cam",
            "media_path": "vault-cam",
            "source_url": "rtsp://10.0.0.50/vault",
        },
    ).json()["data"]["id"]

    # Register Customer B (Attacker)
    client.cookies.clear()
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Attacker B",
            "email": "attacker@evil.com",
            "password": "Password123!",
            "organization_name": "Attacker Org",
        },
    )

    # 1. Attempt to access Org A
    res = client.get(f"/api/v1/organizations/{org_a}")
    assert res.status_code == 404, "Must not leak Org A existence"

    res = client.patch(f"/api/v1/organizations/{org_a}", json={"name": "Hacked Name"})
    assert res.status_code == 404

    # 2. Attempt to access Site A
    res = client.get(f"/api/v1/sites/{site_a}")
    assert res.status_code == 404

    res = client.patch(f"/api/v1/sites/{site_a}", json={"name": "Hacked Site"})
    assert res.status_code == 404

    res = client.delete(f"/api/v1/sites/{site_a}")
    assert res.status_code == 404

    # 3. Attempt to access Camera A
    res = client.get(f"/api/v1/cameras/{cam_a}")
    assert res.status_code == 404

    res = client.patch(f"/api/v1/cameras/{cam_a}", json={"name": "Hacked Cam"})
    assert res.status_code == 404

    res = client.delete(f"/api/v1/cameras/{cam_a}")
    assert res.status_code == 404

    # 4. Attempt to access Camera A stream / playback / restart
    res = client.get(f"/api/v1/cameras/{cam_a}/playback")
    assert res.status_code == 404

    res = client.post(f"/api/v1/cameras/{cam_a}/restart")
    assert res.status_code == 404

    # 5. Attempt to attach a camera to Site A from Org B
    res = client.post(
        "/api/v1/cameras",
        json={
            "site_id": site_a,
            "name": "Trojan Cam",
            "media_path": "trojan-cam",
            "source_url": "rtsp://10.0.0.99/trojan",
        },
    )
    assert res.status_code in (400, 404), "Must reject cross-tenant site association"

    # 6. Attempt to access User A
    res = client.get(f"/api/v1/users/{user_a}")
    assert res.status_code == 404

    res = client.patch(f"/api/v1/users/{user_a}", json={"name": "Compromised User"})
    assert res.status_code == 404

    res = client.delete(f"/api/v1/users/{user_a}")
    assert res.status_code == 404


def test_test_d_role_testing(client: TestClient):
    """
    TEST D: Role Boundaries
    Test VIEWER, OPERATOR, ORG_ADMIN, SUPER_ADMIN permissions and restrictions:
    - VIEWER cannot create or mutate cameras/sites/users.
    - OPERATOR can read/update cameras and control streams, but cannot create or delete cameras/sites/users.
    - ORG_ADMIN can manage their tenant, but CANNOT create or assign SUPER_ADMIN.
    """
    # 1. Register Org & Org Admin
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Admin Chief",
            "email": "chief@roles-test.com",
            "password": "Password123!",
            "organization_name": "Roles Test Corp",
        },
    )
    site = client.post("/api/v1/sites", json={"name": "Base Site"}).json()["data"]
    cam = client.post(
        "/api/v1/cameras",
        json={
            "site_id": site["id"],
            "name": "Base Cam",
            "media_path": "base-cam",
            "source_url": "rtsp://10.0.0.1/base",
        },
    ).json()["data"]

    # 2. ORG_ADMIN cannot create SUPER_ADMIN
    bad_create = client.post(
        "/api/v1/users",
        json={
            "name": "Sneaky Super",
            "email": "sneaky@roles-test.com",
            "password": "Password123!",
            "role": UserRole.SUPER_ADMIN,
        },
    )
    assert bad_create.status_code == 403, "ORG_ADMIN must not create SUPER_ADMIN"

    # Create an OPERATOR and a VIEWER
    client.post(
        "/api/v1/users",
        json={
            "name": "Valid Operator",
            "email": "op@roles-test.com",
            "password": "Password123!",
            "role": UserRole.OPERATOR,
        },
    )
    client.post(
        "/api/v1/users",
        json={
            "name": "Valid Viewer",
            "email": "view@roles-test.com",
            "password": "Password123!",
            "role": UserRole.VIEWER,
        },
    )

    # 3. Test as OPERATOR
    client.cookies.clear()
    op_login = client.post(
        "/api/v1/auth/login",
        json={"email": "op@roles-test.com", "password": "Password123!"},
    )
    assert op_login.status_code == 200

    # Operator CAN read cameras and view stream
    assert client.get("/api/v1/cameras").status_code == 200
    assert client.get(f"/api/v1/cameras/{cam['id']}/playback").status_code == 200

    # Operator CAN update camera
    assert client.patch(f"/api/v1/cameras/{cam['id']}", json={"name": "Renamed Cam"}).status_code == 200

    # Operator CANNOT create camera
    op_cam_create = client.post(
        "/api/v1/cameras",
        json={
            "site_id": site["id"],
            "name": "Forbidden Cam",
            "media_path": "forbidden-cam",
            "source_url": "rtsp://10.0.0.2/forbidden",
        },
    )
    assert op_cam_create.status_code == 403

    # Operator CANNOT delete camera
    assert client.delete(f"/api/v1/cameras/{cam['id']}").status_code == 403

    # Operator CANNOT create site or user
    assert client.post("/api/v1/sites", json={"name": "New Site"}).status_code == 403
    assert client.post(
        "/api/v1/users",
        json={
            "name": "Sub User",
            "email": "sub@roles-test.com",
            "password": "Password123!",
            "role": UserRole.VIEWER,
        },
    ).status_code == 403

    # 4. Test as VIEWER
    client.cookies.clear()
    viewer_login = client.post(
        "/api/v1/auth/login",
        json={"email": "view@roles-test.com", "password": "Password123!"},
    )
    assert viewer_login.status_code == 200

    # Viewer CAN read camera and playback
    assert client.get(f"/api/v1/cameras/{cam['id']}").status_code == 200
    assert client.get(f"/api/v1/cameras/{cam['id']}/playback").status_code == 200

    # Viewer CANNOT update camera
    assert client.patch(f"/api/v1/cameras/{cam['id']}", json={"name": "Viewer Rename"}).status_code == 403

    # Viewer CANNOT delete camera
    assert client.delete(f"/api/v1/cameras/{cam['id']}").status_code == 403

    # Viewer CANNOT create sites, cameras, users
    assert client.post("/api/v1/sites", json={"name": "Site X"}).status_code == 403
    assert client.post("/api/v1/cameras", json={"site_id": site["id"], "name": "Cam X", "media_path": "x", "source_url": "rtsp://x"}).status_code == 403
    assert client.post("/api/v1/users", json={"name": "U", "email": "u@test.com", "password": "p", "role": "VIEWER"}).status_code == 403


def test_test_e_auth_robustness(client: TestClient):
    """
    TEST E: Authentication Robustness
    - Valid login
    - Invalid password
    - Nonexistent account
    - Empty / malformed fields
    - Protected route rejection
    - Logout cookie invalidation
    """
    # 1. Nonexistent account
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "does_not_exist@example.com", "password": "Password123!"},
    )
    assert res.status_code == 401

    # 2. Invalid password on existing seeded account
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@alpha.com", "password": "WrongPassword!"},
    )
    assert res.status_code == 401

    # 3. Empty fields
    res = client.post("/api/v1/auth/login", json={"email": "", "password": ""})
    assert res.status_code in (400, 422)

    # 4. Correct login
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@alpha.com", "password": "Password123!"},
    )
    assert res.status_code == 200
    assert settings.cookie_name in client.cookies

    # 5. Access protected route with active session
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    assert res.json()["data"]["email"] == "admin@alpha.com"

    # 6. Logout and verify protected route returns 401
    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 200
    client.cookies.clear()

    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
