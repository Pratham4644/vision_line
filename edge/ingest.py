#!/usr/bin/env python3
"""Edge FFmpeg Gateway / Ingest Service.

Ingests remote RTSP camera streams and publishes them via authenticated RTSP/TCP
to the MediaMTX streaming server.

Design Principles:
- Zero business logic, zero database interaction, zero user auth.
- Subprocess isolation: strictly no shell=True.
- Bounded exponential backoff on disconnects (2s, 4s, 8s, 16s, max 30s).
- Credential safety: passwords never leak into logs or command tracebacks.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from urllib.parse import quote_plus, urlparse, urlunparse

MEDIA_PATH_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger("camera.edge.ingest")


def validate_media_path(media_path: str) -> str:
    """Validates that the media path adheres to ^[a-zA-Z0-9_-]+$."""
    if not media_path or not MEDIA_PATH_REGEX.match(media_path):
        raise ValueError(
            f"Invalid media_path '{media_path}'. Must match regex ^[a-zA-Z0-9_-]+$ and contain no traversal characters."
        )
    return media_path


def calculate_backoff(attempt: int, base: float = 2.0, max_backoff: float = 30.0) -> float:
    """Calculates bounded exponential backoff delay."""
    return min(base * (2 ** attempt), max_backoff)



def build_publish_url(
    host: str,
    port: int,
    media_path: str,
    username: str = "",
    password: str = "",
) -> tuple[str, str]:
    """Constructs the authenticated RTSP publish URL and its redacted log-safe representation.

    Returns:
        (authenticated_url, redacted_url)
    """
    clean_path = validate_media_path(media_path)
    clean_host = host.strip()

    if username and password:
        enc_user = quote_plus(username)
        enc_pass = quote_plus(password)
        auth_url = f"rtsp://{enc_user}:{enc_pass}@{clean_host}:{port}/{clean_path}"
        redacted_url = f"rtsp://{enc_user}:***@{clean_host}:{port}/{clean_path}"
    elif username:
        enc_user = quote_plus(username)
        auth_url = f"rtsp://{enc_user}@{clean_host}:{port}/{clean_path}"
        redacted_url = auth_url
    else:
        auth_url = f"rtsp://{clean_host}:{port}/{clean_path}"
        redacted_url = auth_url

    return auth_url, redacted_url


def build_ffmpeg_command(source_url: str, publish_url: str) -> list[str]:
    """Constructs the FFmpeg command line arguments array.

    Enforces TCP RTSP transport, H.264 stream copy (no transcoding),
    and strips audio unless specifically needed.
    """
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    return [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-nostdin",
        "-rtsp_transport",
        "tcp",
        "-i",
        source_url,
        "-c:v",
        "copy",
        "-an",
        "-f",
        "rtsp",
        "-rtsp_transport",
        "tcp",
        publish_url,
    ]


class EdgeIngestGateway:
    def __init__(
        self,
        camera_id: str,
        source_url: str,
        media_path: str,
        mediamtx_host: str,
        mediamtx_port: int,
        publish_username: str = "",
        publish_password: str = "",
    ):
        self.camera_id = camera_id.strip()
        self.source_url = source_url.strip()
        self.media_path = validate_media_path(media_path)
        self.mediamtx_host = mediamtx_host.strip()
        self.mediamtx_port = mediamtx_port
        self.publish_username = publish_username.strip()
        self.publish_password = publish_password.strip()

        self._running = False
        self._current_proc: subprocess.Popen | None = None
        self._restart_count = 0

    def stop(self):
        """Signals the gateway to terminate the ingest process and stop reconnection."""
        LOGGER.info(
            "camera_id=%s path=%s state=stopping message='Shutdown signal received'",
            self.camera_id,
            self.media_path,
        )
        self._running = False
        if self._current_proc and self._current_proc.poll() is None:
            try:
                self._current_proc.terminate()
                self._current_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                LOGGER.warning(
                    "camera_id=%s path=%s state=killing message='FFmpeg did not exit gracefully, force killing'",
                    self.camera_id,
                    self.media_path,
                )
                self._current_proc.kill()
            except Exception as exc:
                LOGGER.error("Error terminating FFmpeg: %s", exc)

    def run(self):
        """Starts the supervised ingest loop with bounded exponential backoff."""
        self._running = True
        backoff_delay = 2.0
        max_backoff = 30.0

        publish_url, redacted_publish_url = build_publish_url(
            self.mediamtx_host,
            self.mediamtx_port,
            self.media_path,
            self.publish_username,
            self.publish_password,
        )

        LOGGER.info(
            "camera_id=%s path=%s target=%s state=gateway_initialized",
            self.camera_id,
            self.media_path,
            redacted_publish_url,
        )

        while self._running:
            cmd = build_ffmpeg_command(self.source_url, publish_url)
            start_time = time.time()

            LOGGER.info(
                "camera_id=%s path=%s restart_count=%d state=connecting",
                self.camera_id,
                self.media_path,
                self._restart_count,
            )

            try:
                self._current_proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                pid = self._current_proc.pid

                LOGGER.info(
                    "camera_id=%s path=%s pid=%d restart_count=%d state=publishing",
                    self.camera_id,
                    self.media_path,
                    pid,
                    self._restart_count,
                )

                # Monitor process until it exits or stop() is requested
                while self._running and self._current_proc.poll() is None:
                    time.sleep(1.0)
                    # If stream has been stable for > 60 seconds, reset backoff delay
                    if time.time() - start_time > 60.0 and backoff_delay > 2.0:
                        backoff_delay = 2.0

                exit_code = self._current_proc.poll()
                stderr_output = ""
                if self._current_proc.stderr:
                    stderr_output = self._current_proc.stderr.read()[:500].strip()

                if not self._running:
                    LOGGER.info(
                        "camera_id=%s path=%s pid=%d exit_code=%s state=stopped",
                        self.camera_id,
                        self.media_path,
                        pid,
                        exit_code,
                    )
                    break

                LOGGER.warning(
                    "camera_id=%s path=%s pid=%d exit_code=%s state=process_exited reason='%s'",
                    self.camera_id,
                    self.media_path,
                    pid,
                    exit_code,
                    stderr_output.replace("\n", " "),
                )

            except Exception as exc:
                LOGGER.error(
                    "camera_id=%s path=%s state=spawn_failed error='%s'",
                    self.camera_id,
                    self.media_path,
                    str(exc),
                )

            self._restart_count += 1

            if self._running:
                LOGGER.info(
                    "camera_id=%s path=%s state=reconnect_waiting delay=%.1fs restart_count=%d",
                    self.camera_id,
                    self.media_path,
                    backoff_delay,
                    self._restart_count,
                )
                # Bounded sleep allowing prompt interrupt
                slept = 0.0
                while self._running and slept < backoff_delay:
                    time.sleep(0.5)
                    slept += 0.5

                # Exponential backoff progression: 2s -> 4s -> 8s -> 16s -> 30s max
                backoff_delay = min(backoff_delay * 2.0, max_backoff)


def main():
    camera_id = os.getenv("EDGE_CAMERA_ID", "camera-001")
    source_url = os.getenv("EDGE_SOURCE_URL")
    media_path = os.getenv("EDGE_MEDIA_PATH", "camera-001")
    mediamtx_host = os.getenv("MEDIAMTX_HOST", "127.0.0.1")
    mediamtx_port = int(os.getenv("MEDIAMTX_RTSP_PORT", "8554"))
    pub_username = os.getenv("MEDIAMTX_PUBLISH_USERNAME", "edge_publisher")
    pub_password = os.getenv("MEDIAMTX_PUBLISH_PASSWORD", "")

    if not source_url:
        LOGGER.critical("Missing required environment variable 'EDGE_SOURCE_URL'.")
        sys.exit(1)

    try:
        validate_media_path(media_path)
    except ValueError as exc:
        LOGGER.critical("Configuration error: %s", exc)
        sys.exit(1)

    gateway = EdgeIngestGateway(
        camera_id=camera_id,
        source_url=source_url,
        media_path=media_path,
        mediamtx_host=mediamtx_host,
        mediamtx_port=mediamtx_port,
        publish_username=pub_username,
        publish_password=pub_password,
    )

    def sig_handler(signum, frame):
        gateway.stop()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    gateway.run()


if __name__ == "__main__":
    main()
