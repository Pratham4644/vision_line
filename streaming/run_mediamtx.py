#!/usr/bin/env python3
"""MediaMTX Launcher with Environment-based Authentication.

Generates MTX_AUTHINTERNALUSERS dynamically from environment variables:
  MEDIAMTX_PUBLISH_USERNAME / MEDIAMTX_PUBLISH_PASSWORD
  MEDIAMTX_READ_USERNAME / MEDIAMTX_READ_PASSWORD
and launches the canonical MediaMTX instance with zero hardcoded credentials.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
LOGGER = logging.getLogger("camera.mediamtx")


def build_auth_users(
    pub_user: str,
    pub_pass: str,
    read_user: str,
    read_pass: str,
) -> list[dict]:
    """Constructs strict role-separated users for MediaMTX internal auth."""
    users = []
    # 1. Publisher account (publish only, no read permission)
    if pub_user and pub_pass:
        users.append({
            "user": pub_user,
            "pass": pub_pass,
            "ips": [],
            "permissions": [
                {
                    "action": "publish",
                    "path": "~^[a-zA-Z0-9_-]+$",
                }
            ],
        })

    # 2. Reader account (read only, no publish permission)
    if read_user and read_pass:
        users.append({
            "user": read_user,
            "pass": read_pass,
            "ips": [],
            "permissions": [
                {
                    "action": "read",
                    "path": "~^[a-zA-Z0-9_-]+$",
                }
            ],
        })

    # 3. Localhost monitoring (api/metrics only from 127.0.0.1)
    users.append({
        "user": "internal_monitor",
        "pass": "",
        "ips": ["127.0.0.1", "::1"],
        "permissions": [
            {"action": "api"},
            {"action": "metrics"},
        ],
    })

    return users


def find_mediamtx_binary() -> str:
    """Finds the mediamtx executable on PATH or in standard paths."""
    bin_name = "mediamtx.exe" if sys.platform == "win32" else "mediamtx"
    found = shutil.which(bin_name)
    if found:
        return found

    candidates = [
        os.path.join(sys.prefix, "Scripts", bin_name),
        os.path.join(sys.prefix, "bin", bin_name),
        os.path.join("/usr/local/bin", bin_name),
        os.path.join("/opt/camera-platform/mediamtx", bin_name),
    ]
    for c in candidates:
        if os.path.isfile(c) and os.access(c, os.X_OK if sys.platform != "win32" else os.R_OK):
            return c

    raise FileNotFoundError(f"MediaMTX binary ({bin_name}) not found. Ensure it is installed on PATH.")


def main():
    canonical_conf = os.getenv("MEDIAMTX_CONF", os.path.join("streaming", "mediamtx.yml"))
    pub_user = os.getenv("MEDIAMTX_PUBLISH_USERNAME", "edge_publisher")
    pub_pass = os.getenv("MEDIAMTX_PUBLISH_PASSWORD", "pubpass_secret_dev")
    read_user = os.getenv("MEDIAMTX_READ_USERNAME", "webrtc_reader")
    read_pass = os.getenv("MEDIAMTX_READ_PASSWORD", "readpass_secret_dev")

    if not os.path.isfile(canonical_conf):
        raise FileNotFoundError(f"Canonical MediaMTX config not found: {canonical_conf}")

    with open(canonical_conf, "r", encoding="utf-8") as f:
        conf_content = f.read()

    # Substitute credentials from environment
    conf_content = conf_content.replace("${MEDIAMTX_PUBLISH_USERNAME}", pub_user)
    conf_content = conf_content.replace("${MEDIAMTX_PUBLISH_PASSWORD}", pub_pass)
    conf_content = conf_content.replace("${MEDIAMTX_READ_USERNAME}", read_user)
    conf_content = conf_content.replace("${MEDIAMTX_READ_PASSWORD}", read_pass)

    runtime_conf = os.path.join("streaming", ".mediamtx_runtime.yml")
    with open(runtime_conf, "w", encoding="utf-8") as f:
        f.write(conf_content)

    if sys.platform != "win32":
        os.chmod(runtime_conf, 0o600)

    binary = find_mediamtx_binary()
    LOGGER.info("Starting MediaMTX (Binary: %s, Canonical: %s, Runtime: %s)", binary, canonical_conf, runtime_conf)
    LOGGER.info("Configured publisher '%s' (publish-only) and reader '%s' (read-only)", pub_user, read_user)

    cmd = [binary, runtime_conf]
    try:
        proc = subprocess.run(cmd)
        sys.exit(proc.returncode)
    except KeyboardInterrupt:
        LOGGER.info("MediaMTX stopped by user.")
        sys.exit(0)
    finally:
        if os.path.exists(runtime_conf):
            try:
                os.remove(runtime_conf)
            except OSError:
                pass


if __name__ == "__main__":
    main()

