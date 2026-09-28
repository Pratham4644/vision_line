from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

from backend.app.config import settings


LOGGER = logging.getLogger("camera.services.mediamtx")

SAFE_PATH_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")


class MediaMTXError(Exception):
    """Base exception for MediaMTX control plane operations."""

    pass


class MediaMTXConnectionError(MediaMTXError):
    """Raised when MediaMTX Control API cannot be reached."""

    pass


class MediaMTXProvisionError(MediaMTXError):
    """Raised when MediaMTX rejects path provisioning."""

    pass


def validate_media_path(media_path: str) -> str:
    """
    Validate that a media_path contains only safe characters
    and no directory traversal.
    """
    if not media_path:
        raise ValueError("media_path cannot be empty.")

    clean = media_path.strip()

    if not SAFE_PATH_REGEX.fullmatch(clean):
        raise ValueError(
            f"Invalid media_path '{media_path}'. "
            "Must contain only alphanumeric characters, underscores, and hyphens."
        )

    return clean


class MediaMTXService:
    """
    Control Plane abstraction for MediaMTX v1.21.1 Control API.

    Responsibilities:
    - Provision runtime streaming paths
      POST /v3/config/paths/add/{name}
    - Delete streaming paths
      DELETE /v3/config/paths/delete/{name}
    - Query path configuration
      GET /v3/config/paths/get/{name}
    - Query live runtime status
      GET /v3/paths/get/{name}
    - Update path configuration
      PATCH /v3/config/paths/patch/{name}
    - Perform health checks
      GET /v3/config/global/get

    The MediaMTX Control API is separate from the media-plane
    publisher and reader credentials.

    Control API:
        internal_monitor

    RTSP publisher:
        MEDIAMTX_PUBLISH_USERNAME / MEDIAMTX_PUBLISH_PASSWORD

    WebRTC reader:
        MEDIAMTX_READ_USERNAME / MEDIAMTX_READ_PASSWORD
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 3.0,
    ):
        self._base_url = (
            base_url or settings.mediamtx_api_url
        ).rstrip("/")

        self._timeout = timeout

        # MediaMTX Control API credentials.
        #
        # Current deployment:
        #   username = internal_monitor
        #   password = empty
        #
        # These are deliberately separate from the publisher/reader
        # credentials used by the streaming plane.
        self._api_username = os.getenv(
            "MEDIAMTX_API_USERNAME",
            "internal_monitor",
        )

        self._api_password = os.getenv(
            "MEDIAMTX_API_PASSWORD",
            "",
        )

    @property
    def base_url(self) -> str:
        """Return the MediaMTX Control API base URL."""

        return self._base_url

    def _create_client(self) -> httpx.AsyncClient:
        """
        Create an authenticated HTTP client for the MediaMTX
        Control API.

        Every Control API request must use the same authentication
        mechanism. Centralizing this prevents individual methods from
        accidentally making unauthenticated requests.
        """

        return httpx.AsyncClient(
            timeout=self._timeout,
            auth=httpx.BasicAuth(
                self._api_username,
                self._api_password,
            ),
        )

    async def health_check(self) -> bool:
        """
        Check whether the MediaMTX Control API is reachable
        and responding.
        """

        url = f"{self._base_url}/v3/config/global/get"

        try:
            async with self._create_client() as client:
                resp = await client.get(url)

            if resp.status_code == 200:
                return True

            LOGGER.warning(
                "MediaMTX health check returned HTTP %s: %s",
                resp.status_code,
                resp.text,
            )

            return False

        except httpx.RequestError as exc:
            LOGGER.debug(
                "MediaMTX health check failed at %s: %s",
                url,
                exc,
            )
            return False

    async def provision_path(
        self,
        media_path: str,
        source: str = "publisher",
    ) -> dict[str, Any]:
        """
        Provision a new path in MediaMTX Control API.

        Operation is idempotent.

        If the path already exists:
            HTTP 400/409 + existing-path error
        is treated as a successful no-op.
        """

        clean_path = validate_media_path(media_path)

        url = (
            f"{self._base_url}"
            f"/v3/config/paths/add/{clean_path}"
        )

        payload = {
            "source": source,
        }

        try:
            async with self._create_client() as client:
                resp = await client.post(
                    url,
                    json=payload,
                )

            if resp.status_code in (200, 201):
                LOGGER.info(
                    "MediaMTX path '%s' provisioned successfully",
                    clean_path,
                )

                return {
                    "media_path": clean_path,
                    "status": "provisioned",
                }

            resp_text = resp.text.lower()

            # MediaMTX may return an error when the path already exists.
            if (
                resp.status_code in (400, 409)
                and (
                    "already" in resp_text
                    or "exist" in resp_text
                )
            ):
                LOGGER.info(
                    "MediaMTX path '%s' already exists "
                    "(idempotent provision)",
                    clean_path,
                )

                return {
                    "media_path": clean_path,
                    "status": "already_exists",
                }

            LOGGER.error(
                "MediaMTX rejected path addition for '%s': "
                "HTTP %s - %s",
                clean_path,
                resp.status_code,
                resp.text,
            )

            raise MediaMTXProvisionError(
                f"MediaMTX rejected path addition for "
                f"'{clean_path}' "
                f"(HTTP {resp.status_code}): {resp.text}"
            )

        except httpx.RequestError as exc:
            LOGGER.error(
                "Failed to connect to MediaMTX Control API "
                "at %s: %s",
                url,
                exc,
            )

            raise MediaMTXConnectionError(
                "Could not connect to MediaMTX Control API "
                f"at {self._base_url}: {exc}"
            ) from exc

    async def delete_path(self, media_path: str) -> bool:
        """
        Remove a path from MediaMTX Control API.

        Operation is idempotent.

        HTTP 404 means the path is already gone and is therefore
        treated as successful deletion.
        """

        clean_path = validate_media_path(media_path)

        url = (
            f"{self._base_url}"
            f"/v3/config/paths/delete/{clean_path}"
        )

        try:
            async with self._create_client() as client:
                resp = await client.delete(url)

            if resp.status_code in (200, 204):
                LOGGER.info(
                    "MediaMTX path '%s' deleted successfully",
                    clean_path,
                )
                return True

            if resp.status_code == 404:
                LOGGER.info(
                    "MediaMTX path '%s' not found on delete "
                    "(idempotent)",
                    clean_path,
                )
                return True

            LOGGER.warning(
                "MediaMTX delete path '%s' returned HTTP %s: %s",
                clean_path,
                resp.status_code,
                resp.text,
            )

            return False

        except httpx.RequestError as exc:
            LOGGER.warning(
                "Could not reach MediaMTX Control API to delete "
                "path '%s': %s",
                clean_path,
                exc,
            )

            return False

    async def get_path_config(
        self,
        media_path: str,
    ) -> dict[str, Any] | None:
        """
        Fetch static configuration for a path.

        Endpoint:
            GET /v3/config/paths/get/{name}
        """

        clean_path = validate_media_path(media_path)

        url = (
            f"{self._base_url}"
            f"/v3/config/paths/get/{clean_path}"
        )

        try:
            async with self._create_client() as client:
                resp = await client.get(url)

            if resp.status_code == 200:
                return resp.json()

            LOGGER.debug(
                "MediaMTX path config query for '%s' "
                "returned HTTP %s",
                clean_path,
                resp.status_code,
            )

            return None

        except httpx.RequestError as exc:
            LOGGER.debug(
                "Failed to query MediaMTX path config "
                "for '%s': %s",
                clean_path,
                exc,
            )

            return None

    async def get_path_status(
        self,
        media_path: str,
    ) -> dict[str, Any] | None:
        """
        Fetch live runtime stream status for a path.

        Endpoint:
            GET /v3/paths/get/{name}
        """

        clean_path = validate_media_path(media_path)

        url = (
            f"{self._base_url}"
            f"/v3/paths/get/{clean_path}"
        )

        try:
            async with self._create_client() as client:
                resp = await client.get(url)

            if resp.status_code == 200:
                return resp.json()

            LOGGER.debug(
                "MediaMTX runtime path status query for '%s' "
                "returned HTTP %s",
                clean_path,
                resp.status_code,
            )

            return None

        except httpx.RequestError as exc:
            LOGGER.debug(
                "Failed to query MediaMTX runtime path status "
                "for '%s': %s",
                clean_path,
                exc,
            )

            return None

    async def update_path(
        self,
        media_path: str,
        patch_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update configuration for an existing MediaMTX path.

        Endpoint:
            PATCH /v3/config/paths/patch/{name}
        """

        clean_path = validate_media_path(media_path)

        url = (
            f"{self._base_url}"
            f"/v3/config/paths/patch/{clean_path}"
        )

        try:
            async with self._create_client() as client:
                resp = await client.patch(
                    url,
                    json=patch_data,
                )

            if resp.status_code in (200, 204):
                LOGGER.info(
                    "MediaMTX path '%s' updated successfully",
                    clean_path,
                )

                return {
                    "media_path": clean_path,
                    "status": "updated",
                }

            raise MediaMTXError(
                f"Failed to update MediaMTX path "
                f"'{clean_path}': "
                f"HTTP {resp.status_code} - {resp.text}"
            )

        except httpx.RequestError as exc:
            raise MediaMTXConnectionError(
                "Could not connect to MediaMTX Control API: "
                f"{exc}"
            ) from exc


# Global service instance
mediamtx_service = MediaMTXService()
