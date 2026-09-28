from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, status

from backend.app.auth import (
    verify_edge_gateway_token,
)
from backend.app.config import settings
from backend.app.db import db
from backend.app.models import Camera, IngestMode
from backend.app.services.camera import build_authenticated_source_url

LOGGER = logging.getLogger("camera.edge")

router = APIRouter(
    prefix="/edge",
    tags=["Edge Gateway"],
)


@router.get("/config")
async def get_edge_configuration(
    authorization: str | None = Header(default=None),
):
    """
    Returns enabled EDGE cameras assigned to this gateway.

    The Edge Gateway uses this endpoint to discover what streams
    it should ingest.
    """

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Edge authentication required.",
        )

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid edge authentication header.",
        )

    if not verify_edge_gateway_token(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid edge gateway credentials.",
        )

    cursor = db.cameras.find(
        {
            "edge_gateway_id": settings.edge_gateway_id,
            "ingest_mode": IngestMode.EDGE.value,
            "enabled": True,
        }
    )

    cameras = []

    async for document in cursor:
        camera = Camera(**document)

        source_url = build_authenticated_source_url(camera)

        if not source_url:
            LOGGER.warning(
                "Camera %s has no configured source URL. Skipping.",
                camera.id,
            )
            continue

        cameras.append(
            {
                "camera_id": camera.id,
                "name": camera.name,
                "media_path": camera.media_path,
                "source_url": source_url,
                "resolution": camera.configured_resolution,
                "fps": camera.configured_fps,
                "updated_at": camera.updated_at.isoformat(),
            }
        )

    return {
        "gateway_id": settings.edge_gateway_id,
        "cameras": cameras,
    }
