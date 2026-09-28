from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.auth import get_current_user
from backend.app.db import db
from backend.app.models import Organization, User, UserRole, utc_now
from backend.app.permissions import require_role
from backend.app.schemas import (
    ApiResponse,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)

LOGGER = logging.getLogger("camera.routes.organizations")
router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.post("", response_model=ApiResponse[OrganizationResponse], status_code=status.HTTP_201_CREATED)
async def create_organization(
    req: OrganizationCreate,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN)),
):
    """Creates a new organization (SUPER_ADMIN only)."""
    # Check duplicate name
    existing = await db.organizations.find_one({"name": req.name})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with name '{req.name}' already exists.",
        )

    org = Organization(name=req.name, description=req.description)
    await db.organizations.insert_one(org.model_dump(mode="json"))

    return ApiResponse(
        success=True,
        data=OrganizationResponse(**org.model_dump()),
    )


@router.get("", response_model=ApiResponse[list[OrganizationResponse]])
async def list_organizations(current_user: User = Depends(get_current_user)):
    """
    Lists organizations.
    SUPER_ADMIN can list all organizations.
    Other users can only see their own organization.
    """
    if current_user.role == UserRole.SUPER_ADMIN:
        cursor = db.organizations.find({}).sort("name", 1)
    else:
        cursor = db.organizations.find({"id": current_user.organization_id})

    results = [OrganizationResponse(**doc) async for doc in cursor]
    return ApiResponse(success=True, data=results)


@router.get("/{org_id}", response_model=ApiResponse[OrganizationResponse])
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Fetches organization details.
    Tenant isolated: non-SUPER_ADMIN cannot access other organizations.
    """
    if current_user.role != UserRole.SUPER_ADMIN and current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    doc = await db.organizations.find_one({"id": org_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    return ApiResponse(success=True, data=OrganizationResponse(**doc))


@router.patch("/{org_id}", response_model=ApiResponse[OrganizationResponse])
async def update_organization(
    org_id: str,
    req: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
):
    """
    Updates organization details.
    SUPER_ADMIN can update any org; ORG_ADMIN can only update their own org.
    """
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied.",
        )

    if current_user.role != UserRole.SUPER_ADMIN and current_user.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    doc = await db.organizations.find_one({"id": org_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )

    update_fields: dict[str, str | None] = {"updated_at": utc_now().isoformat()}
    if req.name is not None:
        update_fields["name"] = req.name
    if req.description is not None:
        update_fields["description"] = req.description

    await db.organizations.update_one({"id": org_id}, {"$set": update_fields})
    updated_doc = await db.organizations.find_one({"id": org_id})
    return ApiResponse(success=True, data=OrganizationResponse(**updated_doc))
