from __future__ import annotations

from fastapi import APIRouter

from backend.app.routes.auth import router as auth_router
from backend.app.routes.edge import router as edge_router
from backend.app.routes.cameras import router as cameras_router
from backend.app.routes.logs import router as logs_router
from backend.app.routes.organizations import router as organizations_router
from backend.app.routes.sites import router as sites_router
from backend.app.routes.users import router as users_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(edge_router)
api_v1_router.include_router(organizations_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(sites_router)
api_v1_router.include_router(cameras_router)
api_v1_router.include_router(logs_router)

__all__ = ["api_v1_router"]
