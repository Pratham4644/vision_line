from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.db import db
from backend.app.middleware.error_handler import register_error_handlers
from backend.app.middleware.request_id import RequestIdMiddleware
from backend.app.routes import api_v1_router
from backend.app.routes.health import router as health_router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger("camera.platform")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup: Connect to MongoDB with fail-closed semantics
    LOGGER.info("Starting Remote Camera Streaming Platform (Environment: %s)", settings.app_env)
    db_ok = await db.connect()
    if db_ok:
        try:
            await db.ensure_indexes()
        except Exception as exc:
            LOGGER.error("Failed to ensure database indexes on startup: %s", exc)
    else:
        LOGGER.warning("MongoDB not connected on startup. Database queries will fail closed.")

    yield

    # 2. Shutdown: Cleanly disconnect MongoDB
    LOGGER.info("Shutting down Remote Camera Streaming Platform...")
    await db.close()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

# 1. Middleware: Request ID tracing
app.add_middleware(RequestIdMiddleware)

# 2. Middleware: Restricted CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
)

# 3. Exception handlers
register_error_handlers(app)

# 4. Mount Routes
app.include_router(health_router)
app.include_router(api_v1_router)


@app.get("/", tags=["Root"])
async def root():
    """Root platform status endpoint."""
    return {"name": settings.app_name, "version": "1.0.0", "status": "running"}

