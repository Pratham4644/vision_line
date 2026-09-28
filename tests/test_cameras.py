from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from backend.app.auth import decrypt_camera_credentials
from backend.app.db import db


def test_create_camera_with_credentials(client: TestClient, admin_a_cookies: dict):
    payload = {
        "site_id": "site-alpha-1",
        "name": "Alpha West Perimeter",
        "description": "Gate dome camera",
        "source_protocol": "RTSP",
        "ingest_mode": "EDGE",
        "media_path": "alpha-west-gate",
        "source_url": "rtsp://guard:SecretPass999@192.168.1.55:554/h264",
        "username": "guard",
        "password": "SecretPass999",
        "configured_resolution": "1920x1080",
        "configured_fps": 20.0,
        "enabled": True,
    }
    resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 201
    data = resp.json()["data"]

    # 1. Credentials MUST NOT be in response
    assert "password" not in data
    assert "SecretPass999" not in str(data)
    assert data["has_credentials"] is True
    assert data["name"] == "Alpha West Perimeter"
    assert data["media_path"] == "alpha-west-gate"
    assert data["organization_id"] == "org-alpha"


@pytest.mark.asyncio
async def test_camera_credentials_encrypted_in_db(client: TestClient, admin_a_cookies: dict):
    payload = {
        "site_id": "site-alpha-1",
        "name": "Encrypted Cam",
        "source_protocol": "RTSP",
        "ingest_mode": "EDGE",
        "media_path": "alpha-enc-test",
        "source_url": "rtsp://guard:SecretPass999@192.168.1.55:554/h264",
        "username": "guard",
        "password": "SecretPass999",
    }
    resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 201

    # Fetch camera document from database directly
    doc = await db.cameras.find_one({"media_path": "alpha-enc-test"})
    assert doc is not None

    # Plaintext password must NOT be in document
    assert "password" not in doc
    assert "SecretPass999" not in str(doc)

    # Encrypted credentials_ref must exist and decrypt properly
    assert doc.get("credentials_ref") is not None
    decrypted = decrypt_camera_credentials(doc["credentials_ref"])
    assert decrypted["username"] == "guard"
    assert decrypted["password"] == "SecretPass999"


def test_create_camera_invalid_media_path(client: TestClient, admin_a_cookies: dict):
    payload = {
        "site_id": "site-alpha-1",
        "name": "Injection Test",
        "media_path": "../evil/traversal",
        "source_url": "rtsp://192.168.1.1:554/stream",
    }
    resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 422
    assert "media_path" in str(resp.json()["error"])


def test_list_cameras_scoped_to_org(client: TestClient, admin_a_cookies: dict):
    resp = client.get("/api/v1/cameras", cookies=admin_a_cookies)
    assert resp.status_code == 200
    cameras = resp.json()["data"]
    assert len(cameras) >= 1
    for cam in cameras:
        assert cam["organization_id"] == "org-alpha"
        assert cam["media_path"] != "beta-dock"


def test_get_camera_detail(client: TestClient, admin_a_cookies: dict):
    resp = client.get("/api/v1/cameras/cam-alpha-1", cookies=admin_a_cookies)
    assert resp.status_code == 200
    detail = resp.json()["data"]
    assert detail["id"] == "cam-alpha-1"
    assert "whep_url" in detail
    assert "alpha-gate/whep" in detail["whep_url"]


def test_update_camera_metadata(client: TestClient, admin_a_cookies: dict):
    resp = client.patch(
        "/api/v1/cameras/cam-alpha-1",
        json={"description": "Updated camera notes"},
        cookies=admin_a_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["description"] == "Updated camera notes"


def test_delete_camera(client: TestClient, admin_a_cookies: dict):
    # Create temp camera
    payload = {
        "site_id": "site-alpha-1",
        "name": "Temp Camera",
        "media_path": "temp-cam",
        "source_url": "rtsp://192.168.1.200/live",
    }
    create_resp = client.post("/api/v1/cameras", json=payload, cookies=admin_a_cookies)
    cam_id = create_resp.json()["data"]["id"]

    # Delete
    del_resp = client.delete(f"/api/v1/cameras/{cam_id}", cookies=admin_a_cookies)
    assert del_resp.status_code == 200

    # Ensure deleted
    get_resp = client.get(f"/api/v1/cameras/{cam_id}", cookies=admin_a_cookies)
    assert get_resp.status_code == 404
