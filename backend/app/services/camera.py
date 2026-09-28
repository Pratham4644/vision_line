from __future__ import annotations

import logging
from urllib.parse import quote_plus, urlsplit, urlunsplit

from backend.app.auth import decrypt_camera_credentials
from backend.app.config import settings
from backend.app.models import Camera
from backend.app.schemas import (
    CameraDetailResponse,
    CameraPlaybackResponse,
    CameraResponse,
)
import httpx

LOGGER = logging.getLogger("camera.service")


def sanitize_source_url(raw_url: str) -> tuple[str, str | None, str | None]:
    """
    Parses a source URL, extracts any embedded credentials,
    and returns (clean_url_without_password, extracted_username, extracted_password).
    This ensures that raw passwords NEVER get stored in source_url_template or MongoDB.
    """
    try:
        parts = urlsplit(raw_url)
        extracted_user = parts.username
        extracted_pass = parts.password

        if not extracted_user and not extracted_pass:
            return raw_url, None, None

        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"

        clean_url = urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))
        return clean_url, extracted_user, extracted_pass
    except Exception:
        return raw_url, None, None


def build_authenticated_source_url(camera: Camera) -> str:
    """
    Constructs the operational RTSP source URL with URL-encoded credentials.
    CRITICAL: This is only used internally by ingestion and probing processes.
    It MUST NEVER be returned to clients or logged.
    """
    if not camera.source_url_template:
        return ""

    if not camera.credentials_ref:
        return camera.source_url_template

    creds = decrypt_camera_credentials(camera.credentials_ref)
    username = creds.get("username")
    password = creds.get("password")

    if not username and not password:
        return camera.source_url_template

    try:
        parts = urlsplit(camera.source_url_template)
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"

        # Properly URL-encode username and password
        encoded_user = quote_plus(username) if username else ""
        encoded_pass = quote_plus(password) if password else ""

        if encoded_user and encoded_pass:
            netloc = f"{encoded_user}:{encoded_pass}@{host}"
        elif encoded_user:
            netloc = f"{encoded_user}@{host}"
        else:
            netloc = host

        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception as exc:
        LOGGER.error("Failed to construct authenticated source URL for camera %s: %s", camera.id, exc)
        return camera.source_url_template


def format_camera_response(camera: Camera) -> CameraResponse:
    """Converts a Camera database model to a safe API response with zero credential leakage."""
    return CameraResponse(
        id=camera.id,
        organization_id=camera.organization_id,
        site_id=camera.site_id,
        name=camera.name,
        description=camera.description,
        source_protocol=camera.source_protocol,
        ingest_mode=camera.ingest_mode,
        media_path=camera.media_path,
        enabled=camera.enabled,
        configured_resolution=camera.configured_resolution,
        configured_fps=camera.configured_fps,
        status=camera.status,
        has_credentials=bool(camera.credentials_ref),
        created_at=camera.created_at,
        updated_at=camera.updated_at,
    )


def format_camera_detail(camera: Camera) -> CameraDetailResponse:
    """Formats camera detail response including WebRTC/WHEP playback URL for client."""
    base = format_camera_response(camera)
    public_base = settings.mediamtx_webrtc_public_url.rstrip("/") or f"http://{settings.mediamtx_host}:{settings.mediamtx_webrtc_port}"
    whep_url = f"{public_base}/{camera.media_path}/whep"

    return CameraDetailResponse(
        **base.model_dump(),
        whep_url=whep_url,
        rtsp_playback_url=f"rtsp://{settings.mediamtx_host}:{settings.mediamtx_rtsp_port}/{camera.media_path}",
    )


async def check_media_stream_status(media_path: str) -> tuple[str, str]:
    """Queries MediaMTX internal API for live publisher/stream availability.

    Returns:
        (media_state, ingest_state)
    """
    from backend.app.services.mediamtx import mediamtx_service

    try:
        data = await mediamtx_service.get_path_status(media_path)
        if data:
            is_ready = data.get("ready", False)
            if is_ready:
                return "available", "publishing"
            return "unavailable", "connecting"
        return "unavailable", "disconnected"
    except Exception:
        return "unavailable", "disconnected"



async def format_camera_playback(camera: Camera) -> CameraPlaybackResponse:
    """Formats safe playback configuration with reader-only credentials and live media state."""
    public_base = settings.mediamtx_webrtc_public_url.rstrip("/") or f"http://{settings.mediamtx_host}:{settings.mediamtx_webrtc_port}"
    whep_url = f"{public_base}/{camera.media_path}/whep"
    rtsp_url = f"rtsp://{settings.mediamtx_host}:{settings.mediamtx_rtsp_port}/{camera.media_path}"

    control_state = "enabled" if camera.enabled else "disabled"
    media_state, ingest_state = await check_media_stream_status(camera.media_path)

    # Strictly reader-only credentials for WebRTC/WHEP playback.
    # Browser NEVER receives publisher credentials and cannot publish.
    reader_creds = {
        "username": settings.mediamtx_read_username,
        "password": settings.mediamtx_read_password,
    }

    ice_servers = [
        {"urls": ["stun:stun.l.google.com:19302"]},
    ]

    return CameraPlaybackResponse(
        camera_id=camera.id,
        organization_id=camera.organization_id,
        media_path=camera.media_path,
        whep_url=whep_url,
        rtsp_url=rtsp_url,
        reader_credentials=reader_creds,
        ice_servers=ice_servers,
        control_state=control_state,
        media_state=media_state,
        ingest_state=ingest_state,
    )

