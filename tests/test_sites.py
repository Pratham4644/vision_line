from __future__ import annotations

import pytest
from starlette.testclient import TestClient


def test_create_site_as_admin(client: TestClient, admin_a_cookies: dict):
    payload = {
        "name": "Alpha North Perimeter",
        "description": "Perimeter surveillance zone",
        "location": "North Fence",
    }
    resp = client.post("/api/v1/sites", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Alpha North Perimeter"
    assert data["organization_id"] == "org-alpha"


def test_create_site_duplicate_name_rejected(client: TestClient, admin_a_cookies: dict):
    payload = {
        "name": "Alpha Headquarters",  # Already exists in org-alpha
    }
    resp = client.post("/api/v1/sites", json=payload, cookies=admin_a_cookies)
    assert resp.status_code == 409
    assert "already exists in your organization" in resp.json()["error"]["message"]


def test_list_sites_scoped_to_org(client: TestClient, admin_a_cookies: dict):
    resp = client.get("/api/v1/sites", cookies=admin_a_cookies)
    assert resp.status_code == 200
    sites = resp.json()["data"]
    # All sites returned must belong to org-alpha
    assert len(sites) >= 1
    for site in sites:
        assert site["organization_id"] == "org-alpha"
        assert site["name"] != "Beta Warehouse"


def test_update_site(client: TestClient, admin_a_cookies: dict):
    resp = client.patch(
        "/api/v1/sites/site-alpha-1",
        json={"description": "Updated headquarters description"},
        cookies=admin_a_cookies,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["description"] == "Updated headquarters description"


def test_delete_site_blocked_when_cameras_exist(client: TestClient, admin_a_cookies: dict):
    # site-alpha-1 has cam-alpha-1 attached
    resp = client.delete("/api/v1/sites/site-alpha-1", cookies=admin_a_cookies)
    assert resp.status_code == 400
    assert "currently attached to this site" in resp.json()["error"]["message"]


def test_delete_site_success_when_empty(client: TestClient, admin_a_cookies: dict):
    # Create empty site
    create_resp = client.post("/api/v1/sites", json={"name": "Temporary Empty Site"}, cookies=admin_a_cookies)
    site_id = create_resp.json()["data"]["id"]

    # Delete empty site
    del_resp = client.delete(f"/api/v1/sites/{site_id}", cookies=admin_a_cookies)
    assert del_resp.status_code == 200

    # Ensure site is gone
    get_resp = client.get(f"/api/v1/sites/{site_id}", cookies=admin_a_cookies)
    assert get_resp.status_code == 404
