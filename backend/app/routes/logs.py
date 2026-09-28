from __future__ import annotations

import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Query

from backend.app.db import db
from backend.app.models import User, UserRole
from backend.app.permissions import get_tenant_filter, require_permission
from backend.app.schemas import ApiResponse

LOGGER = logging.getLogger("camera.routes.logs")
router = APIRouter(prefix="/logs", tags=["Audit Logs"])


@router.get("", response_model=ApiResponse[dict])
async def list_logs(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    resource_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    current_user: User = Depends(require_permission("audit:read")),
):
    """
    Lists audit log entries with pagination and tenant isolation.
    """
    base_filter: dict = {}
    if resource_type:
        base_filter["resource_type"] = resource_type
    if action:
        base_filter["action"] = action

    query = get_tenant_filter(current_user, base_filter)
    skip = (page - 1) * page_size

    total = await db.audit_logs.count_documents(query)
    cursor = db.audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(page_size)

    items = []
    async for doc in cursor:
        items.append({
            "id": doc.get("id", ""),
            "organization_id": doc.get("organization_id"),
            "user_id": doc.get("user_id"),
            "action": doc.get("action", ""),
            "resource_type": doc.get("resource_type", ""),
            "resource_id": doc.get("resource_id"),
            "timestamp": doc.get("timestamp", ""),
            "request_id": doc.get("request_id"),
            "details": doc.get("details", {}),
        })

    return ApiResponse(
        success=True,
        data={
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    )
