from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import mongomock
import pytest
from starlette.testclient import TestClient

from backend.app.auth import create_access_token, hash_password
from backend.app.config import settings
from backend.app.db import db
from backend.app.main import app
from backend.app.models import (
    Camera,
    CameraStatus,
    IngestMode,
    Organization,
    Site,
    SourceProtocol,
    User,
    UserRole,
)
from backend.app.services import mediamtx_service
from backend.app.services.mediamtx import MediaMTXConnectionError, MediaMTXProvisionError


class FakeMediaMTXService:
    def __init__(self):
        self.paths: dict[str, str] = {"alpha-gate": "publisher", "beta-dock": "publisher"}
        self.should_fail_provision = False
        self.should_fail_health = False

    async def health_check(self) -> bool:
        return not self.should_fail_health

    async def provision_path(self, path_name: str, source: str = "publisher") -> bool:
        if self.should_fail_provision:
            raise MediaMTXProvisionError("Simulated MediaMTX provision failure")
        self.paths[path_name] = source
        return True

    async def delete_path(self, path_name: str) -> bool:
        self.paths.pop(path_name, None)
        return True

    async def update_path(self, path_name: str, source: str = "publisher") -> bool:
        self.paths[path_name] = source
        return True

    async def get_path_config(self, path_name: str) -> dict | None:
        if path_name in self.paths:
            return {"name": path_name, "source": self.paths[path_name]}
        return None

    async def get_path_status(self, path_name: str) -> dict | None:
        if path_name in self.paths:
            return {"name": path_name, "ready": True, "tracks": ["video"]}
        return None


@pytest.fixture(autouse=True)
def mock_mediamtx(monkeypatch):
    fake = FakeMediaMTXService()
    monkeypatch.setattr(mediamtx_service, "health_check", fake.health_check)
    monkeypatch.setattr(mediamtx_service, "provision_path", fake.provision_path)
    monkeypatch.setattr(mediamtx_service, "delete_path", fake.delete_path)
    monkeypatch.setattr(mediamtx_service, "update_path", fake.update_path)
    monkeypatch.setattr(mediamtx_service, "get_path_config", fake.get_path_config)
    monkeypatch.setattr(mediamtx_service, "get_path_status", fake.get_path_status)
    yield fake


class AsyncCursor:
    def __init__(self, sync_cursor):
        self._cursor = sync_cursor

    def sort(self, *args, **kwargs):
        self._cursor = self._cursor.sort(*args, **kwargs)
        return self

    def skip(self, *args, **kwargs):
        self._cursor = self._cursor.skip(*args, **kwargs)
        return self

    def limit(self, *args, **kwargs):
        self._cursor = self._cursor.limit(*args, **kwargs)
        return self

    def __aiter__(self):
        self._iter = iter(self._cursor)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class AsyncMockCol:
    def __init__(self, sync_col):
        self._col = sync_col

    async def find_one(self, *args, **kwargs):
        return self._col.find_one(*args, **kwargs)

    async def insert_one(self, *args, **kwargs):
        return self._col.insert_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._col.update_one(*args, **kwargs)

    async def delete_one(self, *args, **kwargs):
        return self._col.delete_one(*args, **kwargs)

    async def count_documents(self, *args, **kwargs):
        return self._col.count_documents(*args, **kwargs)

    def find(self, *args, **kwargs):
        return AsyncCursor(self._col.find(*args, **kwargs))

    async def create_indexes(self, *args, **kwargs):
        return []


class AsyncMockDatabase:
    def __init__(self, sync_db):
        self._db = sync_db

    def __getitem__(self, name: str) -> AsyncMockCol:
        return AsyncMockCol(self._db[name])


@pytest.fixture(autouse=True)
def setup_test_db():
    """Sets up an isolated in-memory mock database before each test."""
    mock_client = mongomock.MongoClient()
    sync_db = mock_client["test_camera_platform"]
    db.db = AsyncMockDatabase(sync_db)
    db._connected = True
    orig_ping = db.ping

    async def mock_ping():
        return True

    db.ping = mock_ping

    # 1. Seed Organization A & B
    org_a = Organization(id="org-alpha", name="Alpha Security Corp")
    org_b = Organization(id="org-beta", name="Beta Logistics Inc")
    sync_db["organizations"].insert_one(org_a.model_dump(mode="json"))
    sync_db["organizations"].insert_one(org_b.model_dump(mode="json"))

    # 2. Seed Users
    default_pwd = hash_password("Password123!")
    users = [
        User(
            id="user-super",
            organization_id="org-alpha",
            email="super@platform.local",
            name="Super Admin",
            password_hash=default_pwd,
            role=UserRole.SUPER_ADMIN,
        ),
        User(
            id="user-admin-a",
            organization_id="org-alpha",
            email="admin@alpha.com",
            name="Org A Admin",
            password_hash=default_pwd,
            role=UserRole.ORG_ADMIN,
        ),
        User(
            id="user-operator-a",
            organization_id="org-alpha",
            email="operator@alpha.com",
            name="Org A Operator",
            password_hash=default_pwd,
            role=UserRole.OPERATOR,
        ),
        User(
            id="user-viewer-a",
            organization_id="org-alpha",
            email="viewer@alpha.com",
            name="Org A Viewer",
            password_hash=default_pwd,
            role=UserRole.VIEWER,
        ),
        User(
            id="user-admin-b",
            organization_id="org-beta",
            email="admin@beta.com",
            name="Org B Admin",
            password_hash=default_pwd,
            role=UserRole.ORG_ADMIN,
        ),
        User(
            id="user-viewer-b",
            organization_id="org-beta",
            email="viewer@beta.com",
            name="Org B Viewer",
            password_hash=default_pwd,
            role=UserRole.VIEWER,
        ),
    ]
    for u in users:
        sync_db["users"].insert_one(u.model_dump(mode="json"))

    # 3. Seed Sites
    site_a = Site(id="site-alpha-1", organization_id="org-alpha", name="Alpha Headquarters")
    site_b = Site(id="site-beta-1", organization_id="org-beta", name="Beta Warehouse")
    sync_db["sites"].insert_one(site_a.model_dump(mode="json"))
    sync_db["sites"].insert_one(site_b.model_dump(mode="json"))

    # 4. Seed Cameras
    cam_a = Camera(
        id="cam-alpha-1",
        organization_id="org-alpha",
        site_id="site-alpha-1",
        name="Alpha Gate Cam",
        media_path="alpha-gate",
        source_url_template="rtsp://192.168.1.10:554/live",
        status=CameraStatus.ONLINE,
    )
    cam_b = Camera(
        id="cam-beta-1",
        organization_id="org-beta",
        site_id="site-beta-1",
        name="Beta Dock Cam",
        media_path="beta-dock",
        source_url_template="rtsp://192.168.2.20:554/live",
        status=CameraStatus.ONLINE,
    )
    sync_db["cameras"].insert_one(cam_a.model_dump(mode="json"))
    sync_db["cameras"].insert_one(cam_b.model_dump(mode="json"))

    yield sync_db

    db._connected = False
    db.db = None
    db.ping = orig_ping


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def get_cookies_for_user(user_id: str, email: str, role: UserRole, org_id: str) -> dict[str, str]:
    u = User(
        id=user_id,
        organization_id=org_id,
        email=email,
        name="Test",
        password_hash="",
        role=role,
    )
    token = create_access_token(u)
    return {settings.cookie_name: token}


@pytest.fixture
def super_admin_cookies():
    return get_cookies_for_user("user-super", "super@platform.local", UserRole.SUPER_ADMIN, "org-alpha")


@pytest.fixture
def admin_a_cookies():
    return get_cookies_for_user("user-admin-a", "admin@alpha.com", UserRole.ORG_ADMIN, "org-alpha")


@pytest.fixture
def viewer_a_cookies():
    return get_cookies_for_user("user-viewer-a", "viewer@alpha.com", UserRole.VIEWER, "org-alpha")


@pytest.fixture
def operator_a_cookies():
    return get_cookies_for_user("user-operator-a", "operator@alpha.com", UserRole.OPERATOR, "org-alpha")


@pytest.fixture
def admin_b_cookies():
    return get_cookies_for_user("user-admin-b", "admin@beta.com", UserRole.ORG_ADMIN, "org-beta")


@pytest.fixture
def viewer_b_cookies():
    return get_cookies_for_user("user-viewer-b", "viewer@beta.com", UserRole.VIEWER, "org-beta")
