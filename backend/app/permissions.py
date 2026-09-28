from __future__ import annotations

from typing import Any, Callable
from fastapi import Depends, HTTPException, status

from backend.app.auth import get_current_user
from backend.app.models import User, UserRole

# Explicit role permission sets
ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.SUPER_ADMIN: {
        "org:create",
        "org:read",
        "org:update",
        "org:delete",
        "user:create",
        "user:read",
        "user:update",
        "user:delete",
        "site:create",
        "site:read",
        "site:update",
        "site:delete",
        "camera:create",
        "camera:read",
        "camera:update",
        "camera:delete",
        "stream:read",
        "stream:control",
        "recording:read",
        "recording:delete",
        "audit:read",
        "system:manage",
    },
    UserRole.ORG_ADMIN: {
        "org:read",
        "org:update",
        "user:create",
        "user:read",
        "user:update",
        "user:delete",
        "site:create",
        "site:read",
        "site:update",
        "site:delete",
        "camera:create",
        "camera:read",
        "camera:update",
        "camera:delete",
        "stream:read",
        "stream:control",
        "recording:read",
        "recording:delete",
        "audit:read",
    },
    UserRole.OPERATOR: {
        "org:read",
        "user:read",
        "site:read",
        "camera:read",
        "camera:update",  # Operational updates only (e.g. enable/disable)
        "stream:read",
        "stream:control",
        "recording:read",
    },
    UserRole.VIEWER: {
        "org:read",
        "site:read",
        "camera:read",
        "stream:read",
        "recording:read",
    },
}


def has_permission(role: UserRole, permission: str) -> bool:
    """Checks if a given role possesses the specified permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


def can_manage_role(creator_role: UserRole, target_role: UserRole) -> bool:
    """
    Enforces role hierarchy:
    - SUPER_ADMIN can assign any role.
    - ORG_ADMIN can only assign ORG_ADMIN, OPERATOR, VIEWER (never SUPER_ADMIN).
    - OPERATOR and VIEWER cannot assign roles.
    """
    if creator_role == UserRole.SUPER_ADMIN:
        return True
    if creator_role == UserRole.ORG_ADMIN:
        return target_role in (UserRole.ORG_ADMIN, UserRole.OPERATOR, UserRole.VIEWER)
    return False


def require_role(*allowed_roles: UserRole) -> Callable:
    """Dependency that enforces user role membership."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {[r.value for r in allowed_roles]}",
            )
        return current_user
    return role_checker


def require_permission(permission: str) -> Callable:
    """Dependency that enforces explicit granular permissions."""
    async def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Missing required permission: '{permission}'",
            )
        return current_user
    return permission_checker


def get_tenant_filter(current_user: User, base_filter: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    CRITICAL SERVER-SIDE TENANT ISOLATION:
    Ensures that queries for tenant-owned resources strictly filter by current_user.organization_id.
    Only SUPER_ADMIN may query without forced tenant scoping (or with explicit tenant filter).
    """
    query = dict(base_filter) if base_filter else {}
    if current_user.role == UserRole.SUPER_ADMIN:
        return query

    # Non-superadmin MUST always be scoped to their own organization
    query["organization_id"] = current_user.organization_id
    return query
