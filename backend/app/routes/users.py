from __future__ import annotations

import logging
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.auth import get_current_user, hash_password
from backend.app.db import db
from backend.app.models import User, UserRole, utc_now
from backend.app.permissions import can_manage_role, get_tenant_filter, require_permission, require_role
from backend.app.schemas import ApiResponse, UserCreate, UserResponse, UserUpdate

LOGGER = logging.getLogger("camera.routes.users")
router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def create_user(
    req: UserCreate,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)),
):
    """
    Creates a new user.
    - SUPER_ADMIN can create users in any organization and with any role.
    - ORG_ADMIN can only create users within their own organization and cannot create SUPER_ADMIN.
    """
    # 1. Determine target organization
    if current_user.role == UserRole.SUPER_ADMIN:
        target_org_id = req.organization_id or current_user.organization_id
    else:
        target_org_id = current_user.organization_id

    # 2. Check role hierarchy
    if not can_manage_role(current_user.role, req.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have permission to assign the role '{req.role.value}'.",
        )

    # 3. Verify organization exists
    org_doc = await db.organizations.find_one({"id": target_org_id})
    if not org_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Target organization '{target_org_id}' does not exist.",
        )

    # 4. Check email uniqueness
    existing_user = await db.users.find_one({"email": req.email.lower()})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{req.email}' already exists.",
        )

    # 5. Create user with hashed password
    hashed_pwd = hash_password(req.password)
    user = User(
        organization_id=target_org_id,
        email=req.email.lower(),
        name=req.name,
        password_hash=hashed_pwd,
        role=req.role,
        is_active=True,
    )
    await db.users.insert_one(user.model_dump(mode="json"))

    return ApiResponse(
        success=True,
        data=UserResponse(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
    )


@router.get("", response_model=ApiResponse[list[UserResponse]])
async def list_users(
    organization_id: Annotated[str | None, Query()] = None,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)),
):
    """
    Lists users.
    SUPER_ADMIN can list all or filter by organization_id.
    ORG_ADMIN can only list users in their own organization.
    """
    filter_query: dict = {}
    if current_user.role == UserRole.SUPER_ADMIN:
        if organization_id:
            filter_query["organization_id"] = organization_id
    else:
        filter_query["organization_id"] = current_user.organization_id

    cursor = db.users.find(filter_query).sort("created_at", -1)
    results = [
        UserResponse(
            id=doc["id"],
            organization_id=doc["organization_id"],
            email=doc["email"],
            name=doc["name"],
            role=doc["role"],
            is_active=doc["is_active"],
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )
        async for doc in cursor
    ]
    return ApiResponse(success=True, data=results)


@router.get("/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves user profile.
    Strict tenant isolation: non-SUPER_ADMIN cannot access users outside their organization.
    """
    query = get_tenant_filter(current_user, {"id": user_id})
    doc = await db.users.find_one(query)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Permission check for viewers/operators looking at other users
    if current_user.role not in (UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN) and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    return ApiResponse(
        success=True,
        data=UserResponse(
            id=doc["id"],
            organization_id=doc["organization_id"],
            email=doc["email"],
            name=doc["name"],
            role=doc["role"],
            is_active=doc["is_active"],
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        ),
    )


@router.patch("/{user_id}", response_model=ApiResponse[UserResponse])
async def update_user(
    user_id: str,
    req: UserUpdate,
    current_user: User = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN)),
):
    """
    Updates user account.
    ORG_ADMIN cannot elevate any user to SUPER_ADMIN or modify users from other organizations.
    """
    query = get_tenant_filter(current_user, {"id": user_id})
    doc = await db.users.find_one(query)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Role update validation
    if req.role is not None:
        if not can_manage_role(current_user.role, req.role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have permission to assign role '{req.role.value}'.",
            )

    update_fields: dict = {"updated_at": utc_now().isoformat()}
    if req.name is not None:
        update_fields["name"] = req.name
    if req.email is not None:
        # Check uniqueness
        existing = await db.users.find_one({"email": req.email.lower(), "id": {"$ne": user_id}})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already in use by another user.",
            )
        update_fields["email"] = req.email.lower()
    if req.password is not None:
        update_fields["password_hash"] = hash_password(req.password)
    if req.role is not None:
        update_fields["role"] = req.role.value
    if req.is_active is not None:
        update_fields["is_active"] = req.is_active

    await db.users.update_one(query, {"$set": update_fields})
    updated = await db.users.find_one(query)

    return ApiResponse(
        success=True,
        data=UserResponse(
            id=updated["id"],
            organization_id=updated["organization_id"],
            email=updated["email"],
            name=updated["name"],
            role=updated["role"],
            is_active=updated["is_active"],
            created_at=updated["created_at"],
            updated_at=updated["updated_at"],
        ),
    )


@router.delete("/{user_id}", response_model=ApiResponse[dict[str, str]])
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_permission("user:delete")),
):
    """
    Deletes a user account.
    - Scoped strictly to current user's organization.
    - Cannot delete own account.
    - ORG_ADMIN cannot delete a SUPER_ADMIN.
    """
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account.",
        )

    query = get_tenant_filter(current_user, {"id": user_id})
    target_user_doc = await db.users.find_one(query)
    if not target_user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Protect SUPER_ADMIN from non-SUPER_ADMIN deletion
    if target_user_doc.get("role") == UserRole.SUPER_ADMIN.value and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete a Super Admin user.",
        )

    await db.users.delete_one(query)
    LOGGER.info("User %s deleted by %s", user_id, current_user.email)
    return ApiResponse(success=True, data={"message": "User deleted successfully."})
