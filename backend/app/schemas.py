from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
import re

from backend.app.models import (
    CameraStatus,
    IngestMode,
    RecordingStatus,
    SourceProtocol,
    UserRole,
)

T = TypeVar("T")

SAFE_MEDIA_PATH_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")


class ApiResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(from_attributes=True)
    success: bool = True
    data: T | None = None
    error: dict[str, str | None] | None = None


# --- Auth Schemas ---

class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    organization_name: str = Field(min_length=2, max_length=100)

    @field_validator("name", "organization_name")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Value cannot be blank or whitespace only.")
        return clean


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    current_password: str | None = Field(default=None, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class CurrentUserResponse(BaseModel):
    id: str
    organization_id: str
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime


# --- Organization Schemas ---

class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class OrganizationResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


# --- User Schemas ---

class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.VIEWER
    organization_id: str | None = None  # Only SUPER_ADMIN may supply this


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: UserRole | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: str
    organization_id: str
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --- Site Schemas ---

class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=200)


class SiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=200)


class SiteResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    description: str | None = None
    location: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Camera Schemas ---

class CameraCreate(BaseModel):
    site_id: str
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    source_protocol: SourceProtocol = SourceProtocol.RTSP
    ingest_mode: IngestMode = IngestMode.EDGE
    media_path: str | None = Field(default=None, max_length=64)
    enabled: bool = True

    # Operational/Credential parameters (Encrypted server-side, never exposed back)
    source_url: str = Field(min_length=5, max_length=2048)  # e.g. rtsp://192.168.1.50:554/stream or template
    username: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, max_length=128)

    configured_resolution: str | None = "1920x1080"
    configured_fps: float | None = Field(default=15.0, ge=1.0, le=60.0)

    @field_validator("media_path")
    @classmethod
    def validate_media_path(cls, v: str | None) -> str | None:
        if v is None:
            return None
        clean = v.strip()
        if not clean:
            return None
        if not SAFE_MEDIA_PATH_REGEX.match(clean):
            raise ValueError("media_path may only contain alphanumeric characters, underscores, and hyphens.")
        return clean



class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    site_id: str | None = None
    ingest_mode: IngestMode | None = None
    media_path: str | None = Field(default=None, min_length=2, max_length=64)
    enabled: bool | None = None

    source_url: str | None = Field(default=None, min_length=5, max_length=2048)
    username: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, max_length=128)

    configured_resolution: str | None = None
    configured_fps: float | None = Field(default=None, ge=1.0, le=60.0)

    @field_validator("media_path")
    @classmethod
    def validate_media_path_opt(cls, v: str | None) -> str | None:
        if v is None:
            return v
        clean = v.strip()
        if not SAFE_MEDIA_PATH_REGEX.match(clean):
            raise ValueError("media_path may only contain alphanumeric characters, underscores, and hyphens.")
        return clean


class CameraResponse(BaseModel):
    id: str
    organization_id: str
    site_id: str
    name: str
    description: str | None = None
    source_protocol: SourceProtocol
    ingest_mode: IngestMode
    media_path: str
    enabled: bool
    configured_resolution: str | None = None
    configured_fps: float | None = None
    status: CameraStatus
    has_credentials: bool = False
    created_at: datetime
    updated_at: datetime


class CameraDetailResponse(CameraResponse):
    whep_url: str | None = None
    rtsp_playback_url: str | None = None
    measured_fps: float | None = None
    measured_bitrate: str | None = None


class CameraPlaybackResponse(BaseModel):
    camera_id: str
    organization_id: str
    media_path: str
    whep_url: str
    rtsp_url: str
    reader_credentials: dict[str, str]
    ice_servers: list[dict[str, Any]]
    control_state: str
    media_state: str
    ingest_state: str



# --- Recording Schemas ---

class RecordingResponse(BaseModel):
    id: str
    organization_id: str
    site_id: str
    camera_id: str
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float | None = None
    file_size_bytes: int | None = None
    status: RecordingStatus
    download_url: str | None = None
    created_at: datetime


# --- Health Schemas ---

class PublicHealthResponse(BaseModel):
    status: str = "ok"


class DetailedHealthResponse(BaseModel):
    status: str
    database: bool
    mediamtx: bool | None = None
    timestamp: datetime

