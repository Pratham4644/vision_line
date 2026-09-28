from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from backend.app.db import db
from backend.app.models import User, UserRole
from backend.app.permissions import require_role
from backend.app.schemas import ApiResponse, DetailedHealthResponse, PublicHealthResponse

router = APIRouter(tags=["Health"])


@router.get("/healthz", response_model=PublicHealthResponse)
async def public_health():
    """Minimal unauthenticated public health check for load balancers."""
    return PublicHealthResponse(status="ok")


@router.get("/api/v1/health", response_model=ApiResponse[DetailedHealthResponse])
async def detailed_health(
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)),
):
    """Detailed health check for authorized administrators."""
    from backend.app.services.mediamtx import mediamtx_service

    db_ok = await db.ping()
    mediamtx_ok = await mediamtx_service.health_check()
    overall = "healthy" if db_ok and mediamtx_ok else "degraded"

    return ApiResponse(
        success=True,
        data=DetailedHealthResponse(
            status=overall,
            database=db_ok,
            mediamtx=mediamtx_ok,
            timestamp=datetime.now(timezone.utc),
        ),
    )

