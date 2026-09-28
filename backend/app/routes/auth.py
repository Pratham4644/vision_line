from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Response, status

from pymongo.errors import PyMongoError

from backend.app.auth import (
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    hash_password,
    set_auth_cookie,
    verify_password,
)
from backend.app.db import db, DatabaseConnectionError
from backend.app.models import Organization, User, UserRole, utc_now
from backend.app.schemas import (
    ApiResponse,
    CurrentUserResponse,
    LoginRequest,
    ProfileUpdate,
    RegisterRequest,
)

LOGGER = logging.getLogger("camera.routes.auth")
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=ApiResponse[CurrentUserResponse], status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, response: Response):
    """
    Public customer self-registration:
    - Validates email and organization uniqueness.
    - Creates a new isolated Organization.
    - Creates the user with ORG_ADMIN role for the organization (never SUPER_ADMIN).
    - Uses MongoDB transactions or compensating rollback to guarantee no partial tenant states.
    - Issues a signed JWT and sets a secure HttpOnly session cookie.
    """
    clean_email = req.email.lower().strip()
    clean_org_name = req.organization_name.strip()
    clean_name = req.name.strip()

    try:
        # 1. Pre-check email uniqueness
        existing_user = await db.users.find_one({"email": clean_email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An account with email '{clean_email}' already exists.",
            )

        # 2. Pre-check organization name uniqueness
        existing_org = await db.organizations.find_one({"name": clean_org_name})
        if existing_org:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An organization with name '{clean_org_name}' already exists.",
            )
    except DatabaseConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Cannot register.",
        )

    # 3. Initialize models
    org = Organization(name=clean_org_name)
    hashed_pwd = hash_password(req.password)
    user = User(
        organization_id=org.id,
        email=clean_email,
        name=clean_name,
        password_hash=hashed_pwd,
        role=UserRole.ORG_ADMIN,  # Strictly ORG_ADMIN, never SUPER_ADMIN
        is_active=True,
    )

    # 4. Atomic creation with transaction where supported, and compensating rollback
    created_org = False
    try:
        use_tx = False
        if db.client is not None and hasattr(db.client, "start_session"):
            try:
                async with await db.client.start_session() as session:
                    async with session.start_transaction():
                        await db.organizations.insert_one(org.model_dump(mode="json"), session=session)
                        await db.users.insert_one(user.model_dump(mode="json"), session=session)
                        use_tx = True
            except Exception as tx_err:
                LOGGER.debug("Transaction not available, using compensating write: %s", tx_err)
                use_tx = False

        if not use_tx:
            await db.organizations.insert_one(org.model_dump(mode="json"))
            created_org = True
            try:
                await db.users.insert_one(user.model_dump(mode="json"))
            except Exception as user_err:
                LOGGER.error("User creation failed midway, rolling back organization %s: %s", org.id, user_err)
                await db.organizations.delete_one({"id": org.id})
                raise user_err

    except HTTPException:
        raise
    except PyMongoError as pe:
        if created_org:
            await db.organizations.delete_one({"id": org.id})
        msg = str(pe).lower()
        if "duplicate key" in msg or "11000" in msg:
            if "name" in msg:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"An organization with name '{clean_org_name}' already exists.",
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An account with email '{clean_email}' already exists.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to a database error.",
        )
    except Exception as exc:
        if created_org:
            await db.organizations.delete_one({"id": org.id})
        LOGGER.exception("Unexpected error during customer self-registration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )

    # 5. Issue session JWT and set secure HttpOnly cookie
    token = create_access_token(user)
    set_auth_cookie(response, token)
    LOGGER.info("Customer registered successfully: email=%s org=%s role=ORG_ADMIN", user.email, org.name)

    return ApiResponse(
        success=True,
        data=CurrentUserResponse(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.post("/login", response_model=ApiResponse[CurrentUserResponse])
async def login(req: LoginRequest, response: Response):
    """Authenticates with email and password, setting a secure HttpOnly session cookie."""
    try:
        user_doc = await db.users.find_one({"email": req.email.lower()})
    except DatabaseConnectionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Cannot authenticate.",
        )

    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    user = User(**user_doc)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    # Issue token and set secure HttpOnly cookie
    token = create_access_token(user)
    set_auth_cookie(response, token)

    return ApiResponse(
        success=True,
        data=CurrentUserResponse(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.post("/logout", response_model=ApiResponse[dict[str, str]])
async def logout(response: Response):
    """Terminates session by clearing the HttpOnly cookie."""
    clear_auth_cookie(response)
    return ApiResponse(success=True, data={"message": "Logged out successfully."})


@router.get("/me", response_model=ApiResponse[CurrentUserResponse])
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile verified from the database."""
    return ApiResponse(
        success=True,
        data=CurrentUserResponse(
            id=current_user.id,
            organization_id=current_user.organization_id,
            email=current_user.email,
            name=current_user.name,
            role=current_user.role,
            is_active=current_user.is_active,
            created_at=current_user.created_at,
        ),
    )


@router.patch("/profile", response_model=ApiResponse[CurrentUserResponse])
async def update_profile(
    req: ProfileUpdate,
    current_user: User = Depends(get_current_user),
):
    """Updates user's own profile and/or password."""
    update_fields: dict = {"updated_at": utc_now().isoformat()}

    if req.name is not None and req.name.strip():
        update_fields["name"] = req.name.strip()

    if req.new_password:
        if not req.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required to set a new password.",
            )
        if not verify_password(req.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password verification failed.",
            )
        update_fields["password_hash"] = hash_password(req.new_password)

    if len(update_fields) > 1:
        await db.users.update_one({"id": current_user.id}, {"$set": update_fields})

    updated = await db.users.find_one({"id": current_user.id})
    user = User(**updated)
    return ApiResponse(
        success=True,
        data=CurrentUserResponse(
            id=user.id,
            organization_id=user.organization_id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )
