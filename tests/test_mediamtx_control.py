from __future__ import annotations

import re
import pytest
from starlette.testclient import TestClient

from backend.app.db import db
from backend.app.services.mediamtx import MediaMTXService, MediaMTXError, MediaMTXProvisionError


def test_camera_creation_auto_generates_stable_opaque_media_path(
    client: TestClient, admin_a_cookies: dict, mock_mediamtx
):
    """When media_path is omitted in CameraCreate, backend assigns cam_<uuid4_hex>."""
    payload = {
        "site_id": "site-alpha-1",
        "name": "Auto Path Camera",
        "source_url": "rtsp://192.168.1.101:554/ch0",
    }
    resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 201
    data = resp.json()["data"]

    # Verify format: cam_<32 hex chars>
    media_path = data["media_path"]
    assert re.match(r"^cam_[a-f0-9]{32}$", media_path), f"Unexpected media_path format: {media_path}"
    assert data["name"] == "Auto Path Camera"

    # Verify MediaMTX provision was invoked with this exact media_path
    assert media_path in mock_mediamtx.paths
    assert mock_mediamtx.paths[media_path] == "publisher"


def test_camera_creation_provisions_mediamtx(
    client: TestClient, admin_a_cookies: dict, mock_mediamtx
):
    """Camera creation provisions path on MediaMTX plane."""
    payload = {
        "site_id": "site-alpha-1",
        "name": "Provision Test Cam",
        "media_path": "cam_custom_test_123",
        "source_url": "rtsp://192.168.1.102:554/ch0",
    }
    resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 201

    assert "cam_custom_test_123" in mock_mediamtx.paths
    assert mock_mediamtx.paths["cam_custom_test_123"] == "publisher"


def test_camera_creation_rejects_invalid_site(
    client: TestClient, admin_a_cookies: dict
):
    """Camera creation with nonexistent site_id returns 400."""
    payload = {
        "site_id": "site-nonexistent-999",
        "name": "Invalid Site Cam",
        "source_url": "rtsp://192.168.1.103:554/ch0",
    }
    resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 400
    assert "not found in your organization" in resp.json()["error"]["message"].lower()


def test_camera_creation_cannot_cross_tenant_boundary(
    client: TestClient, admin_a_cookies: dict
):
    """Org A Admin cannot attach a camera to Org B's site."""
    payload = {
        "site_id": "site-beta-1",  # belongs to org-beta
        "name": "Cross Tenant Cam",
        "source_url": "rtsp://192.168.2.100:554/ch0",
    }
    resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 400
    assert "not found in your organization" in resp.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_camera_creation_handles_mediamtx_failure_safely(
    client: TestClient, admin_a_cookies: dict, mock_mediamtx
):
    """If MediaMTX provisioning fails, creation aborts with 502 and no DB camera is saved."""
    mock_mediamtx.should_fail_provision = True

    payload = {
        "site_id": "site-alpha-1",
        "name": "Fail Provision Cam",
        "media_path": "cam_fail_test",
        "source_url": "rtsp://192.168.1.104:554/ch0",
    }
    resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 502
    assert "mediamtx" in resp.json()["error"]["message"].lower()

    # Verify no camera was persisted to DB
    doc = await db.cameras.find_one({"media_path": "cam_fail_test"})
    assert doc is None


@pytest.mark.asyncio
async def test_camera_creation_rollback_on_db_failure(
    client: TestClient, admin_a_cookies: dict, mock_mediamtx, monkeypatch
):
    """If DB insertion fails after MediaMTX provisioning, the MediaMTX path is rolled back."""
    import conftest

    async def mock_insert_fail(*args, **kwargs):
        raise RuntimeError("Simulated MongoDB insert crash")

    monkeypatch.setattr(conftest.AsyncMockCol, "insert_one", mock_insert_fail)

    payload = {
        "site_id": "site-alpha-1",
        "name": "DB Crash Cam",
        "media_path": "cam_db_crash_test",
        "source_url": "rtsp://192.168.1.105:554/ch0",
    }
    resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 500

    # Ensure compensation was executed: path must NOT remain in MediaMTX
    assert "cam_db_crash_test" not in mock_mediamtx.paths


def test_repeated_provisioning_is_idempotent(
    client: TestClient, admin_a_cookies: dict, mock_mediamtx
):
    """Re-provisioning existing path does not raise error and succeeds idempotently."""
    mock_mediamtx.paths["cam_existing_path"] = "publisher"

    payload = {
        "site_id": "site-alpha-1",
        "name": "Existing Path Cam",
        "media_path": "cam_existing_path",
        "source_url": "rtsp://192.168.1.106:554/ch0",
    }
    resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 201
    assert "cam_existing_path" in mock_mediamtx.paths


def test_camera_deletion_removes_mediamtx_path(
    client: TestClient, admin_a_cookies: dict, mock_mediamtx
):
    """Deleting a camera removes its path from MediaMTX and DB."""
    # Create camera
    payload = {
        "site_id": "site-alpha-1",
        "name": "To Delete Cam",
        "media_path": "cam_to_delete_99",
        "source_url": "rtsp://192.168.1.107:554/ch0",
    }
    create_resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    assert create_resp.status_code == 201
    cam_id = create_resp.json()["data"]["id"]
    assert "cam_to_delete_99" in mock_mediamtx.paths

    # Delete camera
    del_resp = client.delete(f"/api/v1/cameras/{cam_id}", cookies=admin_a_cookies)
    assert del_resp.status_code == 200

    # Verify removed from MediaMTX
    assert "cam_to_delete_99" not in mock_mediamtx.paths

    # Verify removed from DB
    get_resp = client.get(f"/api/v1/cameras/{cam_id}", cookies=admin_a_cookies)
    assert get_resp.status_code == 404


def test_camera_disable_and_enable_syncs_mediamtx(
    client: TestClient, admin_a_cookies: dict, mock_mediamtx
):
    """Disabling removes path from MediaMTX; enabling restores path."""
    cam_path = "alpha-gate"
    assert cam_path in mock_mediamtx.paths

    # Disable
    dis_resp = client.post("/api/v1/cameras/cam-alpha-1/disable", cookies=admin_a_cookies)
    assert dis_resp.status_code == 200
    assert dis_resp.json()["data"]["enabled"] is False
    assert cam_path not in mock_mediamtx.paths

    # Enable
    en_resp = client.post("/api/v1/cameras/cam-alpha-1/enable", cookies=admin_a_cookies)
    assert en_resp.status_code == 200
    assert en_resp.json()["data"]["enabled"] is True
    assert cam_path in mock_mediamtx.paths


def test_playback_endpoint_returns_correct_whep_url(
    client: TestClient, admin_a_cookies: dict
):
    """Playback returns authorized WHEP URL strictly derived from camera's media_path."""
    resp = client.get("/api/v1/cameras/cam-alpha-1/playback", cookies=admin_a_cookies)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["camera_id"] == "cam-alpha-1"
    assert data["media_path"] == "alpha-gate"
    assert "/alpha-gate/whep" in data["whep_url"]


def test_playback_endpoint_rejects_unauthorized_and_cross_tenant(
    client: TestClient, admin_a_cookies: dict, admin_b_cookies: dict
):
    """Unauthenticated users and cross-tenant users are rejected from playback."""
    # Unauthenticated
    unauth = client.get("/api/v1/cameras/cam-alpha-1/playback")
    assert unauth.status_code == 401

    # Cross-tenant: Admin B attempting to play Admin A's camera
    cross = client.get("/api/v1/cameras/cam-alpha-1/playback", cookies=admin_b_cookies)
    assert cross.status_code == 404

    # Reverse: Admin A attempting to play Admin B's camera
    cross_rev = client.get("/api/v1/cameras/cam-beta-1/playback", cookies=admin_a_cookies)
    assert cross_rev.status_code == 404


def test_super_admin_can_manage_any_tenant_camera(
    client: TestClient, super_admin_cookies: dict, mock_mediamtx
):
    """SUPER_ADMIN can view and manage cameras across all tenants."""
    # Playback for Alpha
    resp_a = client.get("/api/v1/cameras/cam-alpha-1/playback", cookies=super_admin_cookies)
    assert resp_a.status_code == 200
    assert resp_a.json()["data"]["media_path"] == "alpha-gate"

    # Playback for Beta
    resp_b = client.get("/api/v1/cameras/cam-beta-1/playback", cookies=super_admin_cookies)
    assert resp_b.status_code == 200
    assert resp_b.json()["data"]["media_path"] == "beta-dock"


@pytest.mark.asyncio
async def test_mediamtx_service_direct_unit():
    """Direct unit tests for MediaMTXService HTTP behavior and error handling."""
    service = MediaMTXService(base_url="http://127.0.0.1:9997", timeout=1.0)
    assert service.base_url == "http://127.0.0.1:9997"

    # Invalid path name rejection
    with pytest.raises(ValueError):
        await service.provision_path("")

    with pytest.raises(ValueError):
        await service.provision_path("invalid/path/with/slashes")

    with pytest.raises(ValueError):
        await service.delete_path("")
