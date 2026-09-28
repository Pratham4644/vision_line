from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | edge-agent | %(message)s",
)

LOGGER = logging.getLogger("edge-agent")


# ============================================================
# Paths
# ============================================================

EDGE_DIR = Path(__file__).resolve().parent
INGEST_SCRIPT = EDGE_DIR / "ingest.py"


if not INGEST_SCRIPT.exists():
    raise RuntimeError(
        f"ingest.py not found at {INGEST_SCRIPT}"
    )


# ============================================================
# Configuration
# ============================================================

EDGE_API_URL = os.getenv(
    "EDGE_API_URL",
    "https://camera1.koreacentral.cloudapp.azure.com/api/v1/edge/config",
)

EDGE_GATEWAY_TOKEN = os.getenv("EDGE_GATEWAY_TOKEN", "")

MEDIAMTX_HOST = os.getenv(
    "MEDIAMTX_HOST",
    "20.194.48.89",
)

MEDIAMTX_RTSP_PORT = os.getenv(
    "MEDIAMTX_RTSP_PORT",
    "8554",
)

MEDIAMTX_PUBLISH_USERNAME = os.getenv(
    "MEDIAMTX_PUBLISH_USERNAME",
    "edge-publisher",
)

MEDIAMTX_PUBLISH_PASSWORD = os.getenv(
    "MEDIAMTX_PUBLISH_PASSWORD",
    "",
)

POLL_INTERVAL = int(
    os.getenv("EDGE_POLL_INTERVAL", "10")
)

HTTP_TIMEOUT = int(
    os.getenv("EDGE_HTTP_TIMEOUT", "15")
)


# ============================================================
# Validation
# ============================================================

if not EDGE_GATEWAY_TOKEN:
    raise RuntimeError(
        "EDGE_GATEWAY_TOKEN is not configured."
    )

if not MEDIAMTX_PUBLISH_PASSWORD:
    raise RuntimeError(
        "MEDIAMTX_PUBLISH_PASSWORD is not configured."
    )


# ============================================================
# Helpers
# ============================================================

def camera_fingerprint(camera: dict[str, Any]) -> str:
    """
    Return a stable fingerprint for fields that affect ingestion.

    Do NOT include:
      - name
      - description
      - updated_at
      - status

    Changing those should not restart FFmpeg.
    """

    runtime_config = {
        "source_url": camera.get("source_url"),
        "media_path": camera.get("media_path"),
    }

    payload = json.dumps(
        runtime_config,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


# ============================================================
# Camera Worker
# ============================================================

class CameraWorker:
    """
    Supervises exactly ONE ingest.py process.

    One CameraWorker == one camera.
    """

    def __init__(self, camera: dict[str, Any]):
        self.camera = camera
        self.process: subprocess.Popen | None = None

    @property
    def camera_id(self) -> str:
        return self.camera["camera_id"]

    @property
    def media_path(self) -> str:
        return self.camera["media_path"]

    @property
    def name(self) -> str:
        return self.camera.get(
            "name",
            self.camera_id,
        )

    def is_running(self) -> bool:
        return (
            self.process is not None
            and self.process.poll() is None
        )

    def start(self) -> None:

        if self.is_running():
            return

        LOGGER.info(
            "Starting camera worker: %s (%s)",
            self.name,
            self.camera_id,
        )

        env = os.environ.copy()

        # Camera-specific configuration
        env["EDGE_CAMERA_ID"] = self.camera_id
        env["EDGE_SOURCE_URL"] = self.camera["source_url"]
        env["EDGE_MEDIA_PATH"] = self.media_path

        # Azure MediaMTX configuration
        env["MEDIAMTX_HOST"] = MEDIAMTX_HOST
        env["MEDIAMTX_RTSP_PORT"] = MEDIAMTX_RTSP_PORT
        env["MEDIAMTX_PUBLISH_USERNAME"] = (
            MEDIAMTX_PUBLISH_USERNAME
        )
        env["MEDIAMTX_PUBLISH_PASSWORD"] = (
            MEDIAMTX_PUBLISH_PASSWORD
        )

        # Do not inherit interactive stdin.
        # Do not print the camera URL.
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(INGEST_SCRIPT),
            ],
            env=env,
            stdin=subprocess.DEVNULL,
        )

        LOGGER.info(
            "Camera worker started: %s | PID=%s | path=%s",
            self.camera_id,
            self.process.pid,
            self.media_path,
        )

    def stop(self) -> None:

        if self.process is None:
            return

        if self.process.poll() is None:

            LOGGER.info(
                "Stopping camera worker: %s",
                self.camera_id,
            )

            try:
                self.process.terminate()

                self.process.wait(
                    timeout=10
                )

            except subprocess.TimeoutExpired:

                LOGGER.warning(
                    "Worker did not terminate gracefully. "
                    "Killing: %s",
                    self.camera_id,
                )

                self.process.kill()

                try:
                    self.process.wait(
                        timeout=5
                    )
                except subprocess.TimeoutExpired:
                    pass

        self.process = None

    def update_camera(
        self,
        camera: dict[str, Any],
    ) -> None:

        self.camera = camera


# ============================================================
# Edge Agent
# ============================================================

class EdgeAgent:
    """
    Manages ALL cameras assigned to this gateway.

    One agent process
        ↓
    N CameraWorker instances
        ↓
    N ingest.py processes
        ↓
    N FFmpeg processes
    """

    def __init__(self):

        self.workers: dict[
            str,
            CameraWorker,
        ] = {}

        self.running = True

    # --------------------------------------------------------
    # API
    # --------------------------------------------------------

    def fetch_config(self) -> dict[str, Any]:

        headers = {
            "Authorization": (
                f"Bearer {EDGE_GATEWAY_TOKEN}"
            ),
            "Accept": "application/json",
        }

        response = requests.get(
            EDGE_API_URL,
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )

        response.raise_for_status()

        return response.json()

    # --------------------------------------------------------
    # Reconcile
    # --------------------------------------------------------

    def reconcile(
        self,
        cameras: list[dict[str, Any]],
    ) -> None:

        desired: dict[str, dict[str, Any]] = {}

        for camera in cameras:

            camera_id = camera.get("camera_id")

            if not camera_id:
                LOGGER.warning(
                    "Ignoring camera without camera_id."
                )
                continue

            if not camera.get("media_path"):
                LOGGER.warning(
                    "Ignoring camera %s without media_path.",
                    camera_id,
                )
                continue

            if not camera.get("source_url"):
                LOGGER.warning(
                    "Ignoring camera %s without source_url.",
                    camera_id,
                )
                continue

            desired[camera_id] = camera

        # ----------------------------------------------------
        # Start / update desired cameras
        # ----------------------------------------------------

        for camera_id, camera in desired.items():

            desired_fingerprint = camera_fingerprint(
                camera
            )

            existing = self.workers.get(
                camera_id
            )

            # New camera
            if existing is None:

                worker = CameraWorker(camera)

                worker.start()

                self.workers[camera_id] = {
                    "worker": worker,
                    "fingerprint": desired_fingerprint,
                }

                continue

            worker: CameraWorker = existing["worker"]

            current_fingerprint = existing[
                "fingerprint"
            ]

            # Configuration changed
            if current_fingerprint != desired_fingerprint:

                LOGGER.info(
                    "Runtime configuration changed: %s",
                    camera_id,
                )

                worker.stop()

                worker = CameraWorker(camera)

                worker.start()

                self.workers[camera_id] = {
                    "worker": worker,
                    "fingerprint": desired_fingerprint,
                }

                continue

            # Same configuration but worker crashed
            if not worker.is_running():

                LOGGER.warning(
                    "Camera worker stopped unexpectedly: %s",
                    camera_id,
                )

                worker.update_camera(camera)

                worker.start()

        # ----------------------------------------------------
        # Remove cameras no longer assigned
        # ----------------------------------------------------

        active_camera_ids = set(
            desired.keys()
        )

        existing_camera_ids = set(
            self.workers.keys()
        )

        removed_camera_ids = (
            existing_camera_ids
            - active_camera_ids
        )

        for camera_id in removed_camera_ids:

            LOGGER.info(
                "Camera no longer assigned. "
                "Stopping worker: %s",
                camera_id,
            )

            entry = self.workers.pop(
                camera_id
            )

            worker: CameraWorker = entry[
                "worker"
            ]

            worker.stop()

    # --------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------

    def shutdown(self) -> None:

        if not self.running:
            return

        LOGGER.info(
            "Shutting down Edge Gateway..."
        )

        self.running = False

        for camera_id, entry in list(
            self.workers.items()
        ):

            LOGGER.info(
                "Stopping camera: %s",
                camera_id,
            )

            worker: CameraWorker = entry[
                "worker"
            ]

            worker.stop()

        self.workers.clear()

        LOGGER.info(
            "Edge Gateway stopped."
        )

    # --------------------------------------------------------
    # Main loop
    # --------------------------------------------------------

    def run(self) -> None:

        LOGGER.info(
            "========================================"
        )

        LOGGER.info(
            "Edge Gateway Agent starting"
        )

        LOGGER.info(
            "API: %s",
            EDGE_API_URL,
        )

        LOGGER.info(
            "MediaMTX: %s:%s",
            MEDIAMTX_HOST,
            MEDIAMTX_RTSP_PORT,
        )

        LOGGER.info(
            "Poll interval: %ss",
            POLL_INTERVAL,
        )

        LOGGER.info(
            "========================================"
        )

        while self.running:

            try:

                config = self.fetch_config()

                cameras = config.get(
                    "cameras",
                    [],
                )

                LOGGER.info(
                    "Received %d assigned camera(s)",
                    len(cameras),
                )

                self.reconcile(
                    cameras
                )

            except requests.HTTPError as exc:

                status_code = (
                    exc.response.status_code
                    if exc.response is not None
                    else "unknown"
                )

                LOGGER.error(
                    "Edge API HTTP error: %s",
                    status_code,
                )

            except requests.RequestException as exc:

                LOGGER.error(
                    "Edge API connection error: %s",
                    exc,
                )

            except Exception:

                LOGGER.exception(
                    "Unexpected Edge Agent error"
                )

            time.sleep(
                POLL_INTERVAL
            )


# ============================================================
# Signals
# ============================================================

agent = EdgeAgent()


def handle_shutdown(
    signum,
    frame,
):
    LOGGER.info(
        "Shutdown signal received."
    )

    agent.shutdown()


signal.signal(
    signal.SIGINT,
    handle_shutdown,
)

signal.signal(
    signal.SIGTERM,
    handle_shutdown,
)


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    agent.run()
