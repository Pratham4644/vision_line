from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
import uuid
from pydantic import BaseModel, Field


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ORG_ADMIN = "ORG_ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class CameraStatus(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class IngestMode(StrEnum):
    EDGE = "EDGE"
    DIRECT = "DIRECT"


class SourceProtocol(StrEnum):
    RTSP = "RTSP"


class RecordingStatus(StrEnum):
    RECORDING = "RECORDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class StreamStatus(StrEnum):
    OFFLINE = "OFFLINE"
    STARTING = "STARTING"
    ONLINE = "ONLINE"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


def map_stream_status_to_camera_status(stream_status: StreamStatus | str) -> CameraStatus:
    """Explicit mapping from streaming engine status to camera status without blind enum casting."""
    raw = stream_status.value if isinstance(stream_status, StreamStatus) else str(stream_status).upper()
    match raw:
        case "ONLINE":
            return CameraStatus.ONLINE
        case "STARTING":
            return CameraStatus.UNKNOWN
        case "OFFLINE" | "STOPPING":
            return CameraStatus.OFFLINE
        case "ERROR":
            return CameraStatus.DEGRADED
        case _:
            return CameraStatus.UNKNOWN


class Organization(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    name: str
    description: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class User(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    organization_id: str
    email: str
    name: str
    password_hash: str
    role: UserRole
    is_active: bool = True
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Site(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    organization_id: str
    name: str
    description: str | None = None
    location: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Camera(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    organization_id: str
    site_id: str
    name: str
    description: str | None = None
    source_protocol: SourceProtocol = SourceProtocol.RTSP
    ingest_mode: IngestMode = IngestMode.EDGE

    # Edge gateway responsible for pulling the private camera stream.
    # None is valid for DIRECT cameras.
    edge_gateway_id: str | None = None

    media_path: str
    enabled: bool = True
    credentials_ref: str | None = None
    source_url_template: str | None = None
    configured_resolution: str | None = "1920x1080"
    configured_fps: float | None = 15.0
    status: CameraStatus = CameraStatus.UNKNOWN
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

class Recording(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    organization_id: str
    site_id: str
    camera_id: str
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float | None = None
    file_path: str
    file_size_bytes: int | None = None
    status: RecordingStatus = RecordingStatus.RECORDING
    created_at: datetime = Field(default_factory=utc_now)


class AuditLog(BaseModel):
    id: str = Field(default_factory=generate_uuid)
    organization_id: str | None = None
    user_id: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)
    request_id: str | None = None
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
