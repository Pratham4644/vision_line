from __future__ import annotations

import pytest
from starlette.testclient import TestClient


def test_public_healthz_minimal(client: TestClient):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_admin_detailed_health_requires_auth(client: TestClient):
    # Unauthenticated request must be rejected
    resp = client.get("/api/v1/health")
    assert resp.status_code == 401


def test_admin_detailed_health_authenticated(client: TestClient, admin_a_cookies: dict):
    resp = client.get("/api/v1/health", cookies=admin_a_cookies)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "status" in data
    assert "database" in data
    assert "timestamp" in data
