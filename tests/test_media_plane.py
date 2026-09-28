from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from backend.app.config import settings
from backend.app.db import db
from edge.ingest import (
    build_ffmpeg_command,
    build_publish_url,
    validate_media_path,
)


# --- 1. Edge Command Construction & Safety Tests ---

def test_edge_command_construction():
    source = "rtsp://192.168.1.50:554/stream1"
    publish = "rtsp://pubuser:pubpass@127.0.0.1:8554/cam-front"

    cmd = build_ffmpeg_command(source, publish)

    assert isinstance(cmd, list)
    assert "-rtsp_transport" in cmd
    assert "tcp" in cmd
    assert "-c:v" in cmd
    assert "copy" in cmd
    assert "-an" in cmd
    assert "-f" in cmd
    assert "rtsp" in cmd
    assert source in cmd
    assert publish in cmd


def test_edge_url_encoding_special_chars():
    user = "operator+admin@site#1"
    password = "P@ssw:rd/?#%+test"
    host = "azure.camera.com"
    port = 8554
    path = "cam_alpha-01"

    auth_url, redacted_url = build_publish_url(host, port, path, user, password)

    assert "***" in redacted_url
    assert password not in redacted_url
    assert "%40site%231" in auth_url
    assert "P%40ssw%3Ard%2F%3F%23%25%2Btest" in auth_url
    assert redacted_url.startswith("rtsp://operator%2Badmin%40site%231:***@azure.camera.com:8554/cam_alpha-01")


def test_edge_invalid_media_path_rejection():
    invalid_paths = [
        "../camera",
        "../../etc/passwd",
        "camera/path",
        "camera path",
        "camera?",
        "camera#",
        "camera%",
        "camera;rm",
        "camera&&whoami",
        "",
        "   ",
    ]

    for p in invalid_paths:
        with pytest.raises(ValueError):
            validate_media_path(p)


def test_edge_valid_media_path_accepted():
    valid_paths = [
        "camera-001",
        "camera_front",
        "site1-camera2",
        "CAMERA_123",
        "cam-A_99",
    ]
    for p in valid_paths:
        assert validate_media_path(p) == p


# --- 2. Backend Playback & Tenant Isolation Tests ---

def test_playback_endpoint_success(client: TestClient, admin_a_cookies: dict):
    resp = client.get("/api/v1/cameras/cam-alpha-1/playback", cookies=admin_a_cookies)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["camera_id"] == "cam-alpha-1"
    assert data["organization_id"] == "org-alpha"
    assert data["media_path"] == "alpha-gate"
    assert "/alpha-gate/whep" in data["whep_url"]
    assert "/alpha-gate" in data["rtsp_url"]

    # Security: Browser receives ONLY reader credentials, NEVER publisher credentials
    creds = data["reader_credentials"]
    assert creds["username"] == settings.mediamtx_read_username
    assert creds["password"] == settings.mediamtx_read_password
    assert creds["username"] != settings.mediamtx_publish_username
    assert creds["password"] != settings.mediamtx_publish_password

    assert "control_state" in data
    assert data["control_state"] == "enabled"


def test_playback_viewer_permitted(client: TestClient, viewer_a_cookies: dict):
    # Viewers in the same org are allowed to obtain playback information
    resp = client.get("/api/v1/cameras/cam-alpha-1/playback", cookies=viewer_a_cookies)
    assert resp.status_code == 200
    assert resp.json()["data"]["camera_id"] == "cam-alpha-1"


def test_playback_cross_tenant_rejected(client: TestClient, admin_a_cookies: dict, viewer_a_cookies: dict):
    # cam-beta-1 belongs to org-beta
    # User A (Org A Admin) attempt
    resp = client.get("/api/v1/cameras/cam-beta-1/playback", cookies=admin_a_cookies)
    assert resp.status_code == 404
    assert "not found" in resp.json()["error"]["message"].lower()

    # User A (Org A Viewer) attempt
    resp_viewer = client.get("/api/v1/cameras/cam-beta-1/playback", cookies=viewer_a_cookies)
    assert resp_viewer.status_code == 404


@pytest.mark.asyncio
async def test_playback_disabled_camera_rejected(client: TestClient, admin_a_cookies: dict):
    # Disable cam-alpha-1 in database
    await db.cameras.update_one({"id": "cam-alpha-1"}, {"$set": {"enabled": False}})

    resp = client.get("/api/v1/cameras/cam-alpha-1/playback", cookies=admin_a_cookies)
    assert resp.status_code == 400
    assert "disabled" in resp.json()["error"]["message"].lower()


def test_playback_nonexistent_camera_safe_response(client: TestClient, admin_a_cookies: dict):
    resp = client.get("/api/v1/cameras/cam-nonexistent-999/playback", cookies=admin_a_cookies)
    assert resp.status_code == 404
    assert "not found" in resp.json()["error"]["message"].lower()


def test_edge_exponential_backoff():
    from edge.ingest import calculate_backoff
    assert calculate_backoff(0) == 2.0
    assert calculate_backoff(1) == 4.0
    assert calculate_backoff(2) == 8.0
    assert calculate_backoff(3) == 16.0
    assert calculate_backoff(4) == 30.0  # 32 clamped to 30 max
    assert calculate_backoff(5) == 30.0
    assert calculate_backoff(10) == 30.0


def test_edge_no_shell_true():
    import ast
    with open("edge/ingest.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "shell" and getattr(kw.value, "value", None) is True:
                    pytest.fail("Found shell=True in edge/ingest.py call")



def test_backend_does_not_spawn_remote_ffmpeg():
    import os
    backend_dir = os.path.abspath("backend/app")
    for root, _, files in os.walk(backend_dir):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as py_file:
                    content = py_file.read()
                    assert "ffmpeg" not in content.lower() or "subprocess.popen" not in content.lower(), (
                        f"Prohibited ffmpeg execution detected in backend file: {path}"
                    )

