from __future__ import annotations

import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.db import db
from backend.app.models import Site, User, UserRole, utc_now
from backend.app.permissions import get_tenant_filter, require_permission
from backend.app.schemas import ApiResponse, SiteCreate, SiteResponse, SiteUpdate

LOGGER = logging.getLogger("camera.routes.sites")
router = APIRouter(prefix="/sites", tags=["Sites"])


@router.post("", response_model=ApiResponse[SiteResponse], status_code=status.HTTP_201_CREATED)
async def create_site(
    req: SiteCreate,
    current_user: User = Depends(require_permission("site:create")),
):
    """Creates a new monitoring site strictly bound to current user's organization."""
    # Enforce tenant ownership server-side
    target_org_id = current_user.organization_id

    # Check for duplicate site name within the same organization
    existing = await db.sites.find_one({
        "organization_id": target_org_id,
        "name": req.name,
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Site with name '{req.name}' already exists in your organization.",
        )

    site = Site(
        organization_id=target_org_id,
        name=req.name,
        description=req.description,
        location=req.location,
    )
    await db.sites.insert_one(site.model_dump(mode="json"))

    return ApiResponse(success=True, data=SiteResponse(**site.model_dump()))


@router.get("", response_model=ApiResponse[list[SiteResponse]])
async def list_sites(
    organization_id: Annotated[str | None, Query()] = None,
    current_user: User = Depends(require_permission("site:read")),
):
    """
    Lists sites with strict server-side tenant isolation.
    """
    base_filter: dict = {}
    if current_user.role == UserRole.SUPER_ADMIN and organization_id:
        base_filter["organization_id"] = organization_id

    query = get_tenant_filter(current_user, base_filter)
    cursor = db.sites.find(query).sort("name", 1)
    results = [SiteResponse(**doc) async for doc in cursor]
    return ApiResponse(success=True, data=results)


@router.get("/{site_id}", response_model=ApiResponse[SiteResponse])
async def get_site(
    site_id: str,
    current_user: User = Depends(require_permission("site:read")),
):
    """
    Retrieves site details.
    MANDATORY TENANT ISOLATION: Queries strictly with organization_id.
    """
    query = get_tenant_filter(current_user, {"id": site_id})
    doc = await db.sites.find_one(query)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found.",
        )

    return ApiResponse(success=True, data=SiteResponse(**doc))


@router.patch("/{site_id}", response_model=ApiResponse[SiteResponse])
async def update_site(
    site_id: str,
    req: SiteUpdate,
    current_user: User = Depends(require_permission("site:update")),
):
    """
    Updates site details. Tenant isolated.
    """
    query = get_tenant_filter(current_user, {"id": site_id})
    doc = await db.sites.find_one(query)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found.",
        )

    update_fields: dict = {"updated_at": utc_now().isoformat()}
    if req.name is not None:
        # Check duplicate name in same org
        existing = await db.sites.find_one({
            "organization_id": doc["organization_id"],
            "name": req.name,
            "id": {"$ne": site_id},
        })
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Site with name '{req.name}' already exists in your organization.",
            )
        update_fields["name"] = req.name
    if req.description is not None:
        update_fields["description"] = req.description
    if req.location is not None:
        update_fields["location"] = req.location

    await db.sites.update_one(query, {"$set": update_fields})
    updated = await db.sites.find_one(query)
    return ApiResponse(success=True, data=SiteResponse(**updated))


@router.delete("/{site_id}", response_model=ApiResponse[dict[str, str]])
async def delete_site(
    site_id: str,
    current_user: User = Depends(require_permission("site:delete")),
):
    """
    Deletes site. Rejects deletion if active cameras exist in this site.
    """
    query = get_tenant_filter(current_user, {"id": site_id})
    doc = await db.sites.find_one(query)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found.",
        )

    # Check for existing cameras
    camera_count = await db.cameras.count_documents({
        "site_id": site_id,
        "organization_id": doc["organization_id"],
    })
    if camera_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete site: {camera_count} camera(s) are currently attached to this site.",
        )

    await db.sites.delete_one(query)
    return ApiResponse(success=True, data={"message": "Site deleted successfully."})
