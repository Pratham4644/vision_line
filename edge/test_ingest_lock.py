#!/usr/bin/env python3
"""Isolated tests for per-camera ingest lock path isolation."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

INGEST_PATH = Path(__file__).resolve().parent / "ingest.py"


def load_ingest_module():
    spec = importlib.util.spec_from_file_location("ingest_test", INGEST_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_test"] = module
    spec.loader.exec_module(module)
    return module


class CameraPathIsolationTests(unittest.TestCase):
    def test_lock_paths_unique_per_camera_id(self) -> None:
        ingest = load_ingest_module()
        ids = [
            "80d5abf5-173d-44ff-8e49-50596975fa3a",
            "bf3adced-b145-4a42-8559-192cdc9aedee",
            "231ead0d-3287-4c1e-bb55-9909639129c2",
        ]
        paths = set()
        for camera_id in ids:
            ingest.CAMERA_ID = camera_id
            ingest.init_camera_paths()
            paths.add(ingest.CAMERA_LOCK_PATH)
            paths.add(ingest.FFMPEG_PID_PATH)
        self.assertEqual(len(paths), len(ids) * 2)
        for camera_id in ids:
            expected_key = hashlib.sha256(camera_id.encode("utf-8")).hexdigest()[:16]
            ingest.CAMERA_ID = camera_id
            ingest.init_camera_paths()
            self.assertEqual(ingest.CAMERA_KEY, expected_key)
            self.assertEqual(
                ingest.CAMERA_LOCK_PATH,
                ingest.EDGE_DIR / f".ingest-{expected_key}.lock",
            )
            self.assertEqual(
                ingest.FFMPEG_PID_PATH,
                ingest.EDGE_DIR / f".ffmpeg-{expected_key}.pid",
            )

    def test_paths_not_unknown_when_camera_id_set(self) -> None:
        ingest = load_ingest_module()
        ingest.CAMERA_ID = "80d5abf5-173d-44ff-8e49-50596975fa3a"
        ingest.init_camera_paths()
        self.assertNotIn("unknown", str(ingest.CAMERA_LOCK_PATH))
        self.assertNotIn("uninitialized", str(ingest.CAMERA_LOCK_PATH))

    def test_load_runtime_config_initializes_paths(self) -> None:
        ingest = load_ingest_module()
        ingest.CAMERA_ID = ""
        ingest.MEDIA_PATH = ""
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "EDGE_CAMERA_ID=bf3adced-b145-4a42-8559-192cdc9aedee\n"
                "EDGE_SOURCE_URL=rtsp://192.168.1.14:8080/h264.sdp\n"
                "EDGE_MEDIA_PATH=cam_test\n"
                "MEDIAMTX_HOST=127.0.0.1\n"
                "MEDIAMTX_PUBLISH_PASSWORD=secret\n",
                encoding="utf-8",
            )
            old_argv = sys.argv[:]
            try:
                sys.argv = ["ingest.py"]
                # Patch env loading by setting os.environ directly
                import os

                os.environ["EDGE_CAMERA_ID"] = "bf3adced-b145-4a42-8559-192cdc9aedee"
                os.environ["EDGE_SOURCE_URL"] = "rtsp://192.168.1.14:8080/h264.sdp"
                os.environ["EDGE_MEDIA_PATH"] = "cam_test"
                os.environ["MEDIAMTX_HOST"] = "127.0.0.1"
                os.environ["MEDIAMTX_PUBLISH_PASSWORD"] = "secret"
                ingest.load_runtime_config()
            finally:
                sys.argv = old_argv

        expected_key = hashlib.sha256(
            b"bf3adced-b145-4a42-8559-192cdc9aedee"
        ).hexdigest()[:16]
        self.assertEqual(ingest.CAMERA_KEY, expected_key)
        self.assertEqual(ingest.CAMERA_LOCK_PATH.name, f".ingest-{expected_key}.lock")


class CameraIngestLockBehaviorTests(unittest.TestCase):
    def test_same_camera_second_acquire_fails(self) -> None:
        ingest = load_ingest_module()
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "camera-a.lock"
            lock_a = ingest.CameraIngestLock(lock_path)
            lock_b = ingest.CameraIngestLock(lock_path)
            self.assertTrue(lock_a.acquire())
            self.assertFalse(lock_b.acquire())
            lock_a.release()

    def test_different_cameras_both_acquire(self) -> None:
        ingest = load_ingest_module()
        with tempfile.TemporaryDirectory() as tmp:
            path_a = Path(tmp) / "camera-a.lock"
            path_b = Path(tmp) / "camera-b.lock"
            lock_a = ingest.CameraIngestLock(path_a)
            lock_b = ingest.CameraIngestLock(path_b)
            self.assertTrue(lock_a.acquire())
            self.assertTrue(lock_b.acquire())
            lock_a.release()
            lock_a2 = ingest.CameraIngestLock(path_a)
            lock_b2 = ingest.CameraIngestLock(path_b)
            self.assertTrue(lock_a2.acquire())
            self.assertFalse(lock_b2.acquire())
            lock_a2.release()
            lock_b.release()


if __name__ == "__main__":
    unittest.main()
