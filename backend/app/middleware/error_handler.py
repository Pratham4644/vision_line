from __future__ import annotations

import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from backend.app.config import settings

LOGGER = logging.getLogger("camera.api.error")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": str(exc.detail),
                },
                "request_id": req_id,
            },
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        errors = exc.errors()
        msg = "; ".join(f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in errors[:3])
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": msg or "Invalid request parameters",
                    "details": [{"loc": err["loc"], "msg": err["msg"]} for err in errors[:5]],
                },
                "request_id": req_id,
            },
        )

    @app.exception_handler(KeyError)
    async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": str(exc).strip("'\""),
                },
                "request_id": req_id,
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": {
                    "code": "BAD_REQUEST",
                    "message": str(exc),
                },
                "request_id": req_id,
            },
        )

    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": {
                    "code": "FORBIDDEN",
                    "message": str(exc),
                },
                "request_id": req_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = getattr(request.state, "request_id", None)
        LOGGER.exception("Unhandled server exception on %s [req=%s]", request.url.path, req_id)

        # In production, never return internal stack trace
        msg = "An unexpected internal server error occurred." if settings.app_env == "production" else str(exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": msg,
                },
                "request_id": req_id,
            },
        )
