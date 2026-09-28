from __future__ import annotations

import logging
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.config import settings
from backend.app.auth import encrypt_camera_credentials
from backend.app.db import db
from backend.app.models import (
    Camera,
    CameraStatus,
    IngestMode,
    User,
    UserRole,
    utc_now,
)
from backend.app.permissions import get_tenant_filter, require_permission
from backend.app.schemas import (
    ApiResponse,
    CameraCreate,
    CameraDetailResponse,
    CameraPlaybackResponse,
    CameraResponse,
    CameraUpdate,
)
from backend.app.services.camera import (
    format_camera_detail,
    format_camera_playback,
    format_camera_response,
    sanitize_source_url,
)
from backend.app.services.mediamtx import MediaMTXError, mediamtx_service

LOGGER = logging.getLogger("camera.routes.cameras")
router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.post("", response_model=ApiResponse[CameraResponse], status_code=status.HTTP_201_CREATED)
async def create_camera(
    req: CameraCreate,
    current_user: User = Depends(require_permission("camera:create")),
):
    """
    Creates a new camera and provisions its streaming path in MediaMTX.
    SERVER-SIDE TENANT ENFORCEMENT:
    - organization_id is ALWAYS derived from current_user.
    - site_id MUST belong to current_user's organization.
    - media_path is auto-generated (cam_<UUID>) if not explicitly provided.
    - Stream path is provisioned dynamically via MediaMTX Control API.
    - Credentials are encrypted at application level before saving.
    """
    target_org_id = current_user.organization_id

    # 1. Verify site belongs to the user's organization
    site_doc = await db.sites.find_one({
        "id": req.site_id,
        "organization_id": target_org_id,
    })
    if not site_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Site '{req.site_id}' not found in your organization.",
        )

    # 2. Determine stable media_path (generate cam_<UUID> if not supplied)
    if req.media_path and req.media_path.strip():
        media_path = req.media_path.strip()
    else:
        media_path = f"cam_{uuid.uuid4().hex}"

    # Verify media_path uniqueness within the organization
    existing_path = await db.cameras.find_one({
        "organization_id": target_org_id,
        "media_path": media_path,
    })
    if existing_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Media path '{media_path}' is already in use within your organization.",
        )

    # 3. Sanitize source URL and extract credentials safely
    clean_url, ext_user, ext_pass = sanitize_source_url(req.source_url)
    username = req.username or ext_user
    password = req.password or ext_pass

    # 4. Encrypt credentials if provided
    credentials_ref: str | None = None
    if username or password:
        credentials_ref = encrypt_camera_credentials({
            "username": username or "",
            "password": password or "",
        })

    # 5. Provision streaming path in MediaMTX Control Plane
    # Safe strategy: provision MediaMTX path first; if it fails, abort with 502 Bad Gateway
    if req.enabled:
        try:
            await mediamtx_service.provision_path(media_path, source="publisher")
        except MediaMTXError as exc:
            LOGGER.error("MediaMTX path provisioning failed for '%s': %s", media_path, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to provision streaming path on media plane: {exc}",
            )

    # 6. Construct Camera model and persist to MongoDB
    camera = Camera(
        organization_id=target_org_id,
        site_id=req.site_id,
        name=req.name,
        description=req.description,
        source_protocol=req.source_protocol,
        ingest_mode=req.ingest_mode,
	edge_gateway_id=(
       		settings.edge_gateway_id
       		if req.ingest_mode == IngestMode.EDGE
     	  	else None
    	),
        media_path=media_path,
        enabled=req.enabled,
        credentials_ref=credentials_ref,
        source_url_template=clean_url,
        configured_resolution=req.configured_resolution,
        configured_fps=req.configured_fps,
        status=CameraStatus.UNKNOWN,
    )

    try:
        await db.cameras.insert_one(camera.model_dump(mode="json"))
    except Exception as exc:
        LOGGER.error("MongoDB camera insert failed. Rolling back MediaMTX path '%s': %s", media_path, exc)
        if req.enabled:
            try:
                await mediamtx_service.delete_path(media_path)
            except Exception:
                pass
        raise exc

    return ApiResponse(
        success=True,
        data=format_camera_response(camera),
    )



@router.get("", response_model=ApiResponse[list[CameraResponse]])
async def list_cameras(
    site_id: Annotated[str | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    organization_id: Annotated[str | None, Query()] = None,
    current_user: User = Depends(require_permission("camera:read")),
):
    """
    Lists cameras with strict server-side tenant isolation.
    """
    base_filter: dict = {}
    if site_id:
        base_filter["site_id"] = site_id
    if status_filter:
        base_filter["status"] = status_filter

    if current_user.role == UserRole.SUPER_ADMIN and organization_id:
        base_filter["organization_id"] = organization_id

    query = get_tenant_filter(current_user, base_filter)
    cursor = db.cameras.find(query).sort("created_at", -1)

    results = [format_camera_response(Camera(**doc)) async for doc in cursor]
    return ApiResponse(success=True, data=results)


@router.get("/{camera_id}", response_model=ApiResponse[CameraDetailResponse])
async def get_camera(
    camera_id: str,
    current_user: User = Depends(require_permission("camera:read")),
):
    """
    Retrieves camera details.
    MANDATORY TENANT ISOLATION:
    Always queries with {"id": camera_id, "organization_id": current_user.organization_id}.
    """
    query = get_tenant_filter(current_user, {"id": camera_id})
    doc = await db.cameras.find_one(query)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found.",
        )

    camera = Camera(**doc)
    return ApiResponse(
        success=True,
        data=format_camera_detail(camera),
    )


@router.patch("/{camera_id}", response_model=ApiResponse[CameraResponse])
async def update_camera(
    camera_id: str,
    req: CameraUpdate,
    current_user: User = Depends(require_permission("camera:update")),
):
    """
    Updates camera metadata or configuration.
    Metadata edits (name, description) do not restart streams.
    """
    query = get_tenant_filter(current_user, {"id": camera_id})
    doc = await db.cameras.find_one(query)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found.",
        )

    target_org_id = doc["organization_id"]
    update_fields: dict = {"updated_at": utc_now().isoformat()}

    # Verify site if changing
    if req.site_id is not None:
        site_doc = await db.sites.find_one({
            "id": req.site_id,
            "organization_id": target_org_id,
        })
        if not site_doc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Target site '{req.site_id}' not found in your organization.",
            )
        update_fields["site_id"] = req.site_id

    # Verify media path if changing
    old_media_path = doc.get("media_path")
    if req.media_path is not None and req.media_path != old_media_path:
        existing_path = await db.cameras.find_one({
            "organization_id": target_org_id,
            "media_path": req.media_path,
            "id": {"$ne": camera_id},
        })
        if existing_path:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Media path '{req.media_path}' is already in use in your organization.",
            )
        # Provision new path in MediaMTX first
        try:
            await mediamtx_service.provision_path(req.media_path, source="publisher")
        except MediaMTXError as exc:
            LOGGER.error("Failed to provision new MediaMTX path '%s': %s", req.media_path, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to synchronize updated path on media plane: {exc}",
            )
        update_fields["media_path"] = req.media_path

    # Credential and URL update
    if req.source_url is not None:
        clean_url, ext_user, ext_pass = sanitize_source_url(req.source_url)
        update_fields["source_url_template"] = clean_url
        user_to_save = req.username or ext_user
        pass_to_save = req.password or ext_pass
        if user_to_save or pass_to_save:
            update_fields["credentials_ref"] = encrypt_camera_credentials({
                "username": user_to_save or "",
                "password": pass_to_save or "",
            })
    elif req.username is not None or req.password is not None:
        update_fields["credentials_ref"] = encrypt_camera_credentials({
            "username": req.username or "",
            "password": req.password or "",
        })

    if req.name is not None:
        update_fields["name"] = req.name
    if req.description is not None:
        update_fields["description"] = req.description
    if req.ingest_mode is not None:
        update_fields["ingest_mode"] = req.ingest_mode.value

        if req.ingest_mode == IngestMode.EDGE:
            update_fields["edge_gateway_id"] = settings.edge_gateway_id
        else:
            update_fields["edge_gateway_id"] = None
    if req.enabled is not None:
        update_fields["enabled"] = req.enabled
        # Synchronize enabled state with MediaMTX
        active_path = req.media_path or old_media_path
        if req.enabled:
            try:
                await mediamtx_service.provision_path(active_path, source="publisher")
            except MediaMTXError as exc:
                LOGGER.warning("Could not provision MediaMTX path on enable update: %s", exc)
        else:
            try:
                await mediamtx_service.delete_path(active_path)
            except Exception as exc:
                LOGGER.warning("Could not delete MediaMTX path on disable update: %s", exc)

    if req.configured_resolution is not None:
        update_fields["configured_resolution"] = req.configured_resolution
    if req.configured_fps is not None:
        update_fields["configured_fps"] = req.configured_fps

    await db.cameras.update_one(query, {"$set": update_fields})
    updated_doc = await db.cameras.find_one(query)

    # Clean up old MediaMTX path if media_path changed successfully
    if req.media_path is not None and req.media_path != old_media_path and old_media_path:
        try:
            await mediamtx_service.delete_path(old_media_path)
        except Exception as exc:
            LOGGER.warning("Could not delete old MediaMTX path '%s': %s", old_media_path, exc)

    return ApiResponse(
        success=True,
        data=format_camera_response(Camera(**updated_doc)),
    )


@router.delete("/{camera_id}", response_model=ApiResponse[dict[str, str]])
async def delete_camera(
    camera_id: str,
    current_user: User = Depends(require_permission("camera:delete")),
):
    """
    Deletes camera. Scoped strictly to current user's organization.
    Removes the streaming path from MediaMTX and deletes the camera document from MongoDB.
    """
    query = get_tenant_filter(current_user, {"id": camera_id})
    doc = await db.cameras.find_one(query)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found.",
        )

    camera = Camera(**doc)

    # 1. Remove corresponding path from MediaMTX
    try:
        await mediamtx_service.delete_path(camera.media_path)
    except Exception as exc:
        LOGGER.warning("Could not delete MediaMTX path '%s' during camera deletion: %s", camera.media_path, exc)

    # 2. Remove camera from MongoDB
    await db.cameras.delete_one(query)
    return ApiResponse(success=True, data={"message": "Camera deleted successfully."})


@router.get("/{camera_id}/playback", response_model=ApiResponse[CameraPlaybackResponse])
async def get_camera_playback(
    camera_id: str,
    current_user: User = Depends(require_permission("camera:read")),
):
    """
    Returns authorized WebRTC/WHEP playback configuration for a camera.
    Scoped strictly to the user's organization.
    Returns ONLY reader credentials. The browser NEVER receives publisher credentials.
    """
    query = get_tenant_filter(current_user, {"id": camera_id})
    doc = await db.cameras.find_one(query)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found.",
        )

    camera = Camera(**doc)
    if not camera.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera is currently disabled. Playback is not available.",
        )

    playback_data = await format_camera_playback(camera)
    return ApiResponse(success=True, data=playback_data)


@router.post("/{camera_id}/enable", response_model=ApiResponse[CameraResponse])
async def enable_camera(
    camera_id: str,
    current_user: User = Depends(require_permission("camera:update")),
):
    """Enables a camera for streaming and provisions its MediaMTX path."""
    query = get_tenant_filter(current_user, {"id": camera_id})
    doc = await db.cameras.find_one(query)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found.")

    camera = Camera(**doc)

    # Provision path in MediaMTX
    try:
        await mediamtx_service.provision_path(camera.media_path, source="publisher")
    except MediaMTXError as exc:
        LOGGER.error("Failed to provision MediaMTX path on enable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to enable stream on media plane: {exc}",
        )

    await db.cameras.update_one(query, {"$set": {"enabled": True, "updated_at": utc_now().isoformat()}})
    updated = await db.cameras.find_one(query)
    return ApiResponse(success=True, data=format_camera_response(Camera(**updated)))


@router.post("/{camera_id}/disable", response_model=ApiResponse[CameraResponse])
async def disable_camera(
    camera_id: str,
    current_user: User = Depends(require_permission("camera:update")),
):
    """Disables a camera from streaming and removes its MediaMTX path."""
    query = get_tenant_filter(current_user, {"id": camera_id})
    doc = await db.cameras.find_one(query)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found.")

    camera = Camera(**doc)

    # Remove path from MediaMTX to cut off live streaming / publishing
    try:
        await mediamtx_service.delete_path(camera.media_path)
    except Exception as exc:
        LOGGER.warning("Could not delete MediaMTX path on disable: %s", exc)

    await db.cameras.update_one(query, {"$set": {"enabled": False, "updated_at": utc_now().isoformat()}})
    updated = await db.cameras.find_one(query)
    return ApiResponse(success=True, data=format_camera_response(Camera(**updated)))



@router.post("/{camera_id}/restart", response_model=ApiResponse[CameraResponse])
async def restart_camera_stream(
    camera_id: str,
    current_user: User = Depends(require_permission("stream:control")),
):
    """Restarts the ingestion stream for a camera by toggling its status."""
    query = get_tenant_filter(current_user, {"id": camera_id})
    doc = await db.cameras.find_one(query)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found.")

    camera = Camera(**doc)
    if not camera.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot restart a disabled camera. Enable it first.",
        )

    # Update timestamp to signal edge gateway to cycle the stream
    await db.cameras.update_one(query, {"$set": {
        "status": CameraStatus.UNKNOWN.value,
        "updated_at": utc_now().isoformat(),
    }})
    updated = await db.cameras.find_one(query)
    LOGGER.info("Stream restart initiated for camera %s by user %s", camera_id, current_user.email)
    return ApiResponse(success=True, data=format_camera_response(Camera(**updated)))


@router.post("/{camera_id}/test", response_model=ApiResponse[dict])
async def test_camera_connection(
    camera_id: str,
    current_user: User = Depends(require_permission("camera:read")),
):
    """Tests media stream availability by querying MediaMTX API."""
    query = get_tenant_filter(current_user, {"id": camera_id})
    doc = await db.cameras.find_one(query)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found.")

    camera = Camera(**doc)
    from backend.app.services.camera import check_media_stream_status
    media_state, ingest_state = await check_media_stream_status(camera.media_path)

    ok = media_state == "available" and ingest_state == "publishing"
    message = (
        f"Stream '{camera.media_path}' is live and publishing."
        if ok
        else f"Stream '{camera.media_path}' is {media_state} (ingest: {ingest_state})."
    )

    return ApiResponse(success=True, data={"ok": ok, "message": message}
)
