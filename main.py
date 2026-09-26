import requests

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Camera
from stream_manager import stream_manager


app = FastAPI(
    title="AI CCTV Platform",
    version="0.2.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Request Schemas
# ============================================================

class CameraCreate(BaseModel):
    camera_id: str
    name: str

    manufacturer: str | None = None

    protocol: str

    host: str | None = None
    port: int | None = None

    stream_url: str

    username: str | None = None
    password: str | None = None


# ============================================================
# MediaMTX Configuration
# ============================================================

MEDIAMTX_API = "http://127.0.0.1:9997"

MEDIAMTX_USERNAME = "PS"

# Keep your existing local MediaMTX password here.
# Do not expose it in API responses or frontend code.
MEDIAMTX_PASSWORD = "Sasha123"


# ============================================================
# Database
# ============================================================

def get_db():
    return SessionLocal()


# ============================================================
# Camera Source URL
# ============================================================

def build_camera_url(camera: Camera):

    if not camera.stream_url:
        raise HTTPException(
            status_code=400,
            detail="Camera stream URL is not configured"
        )

    stream_url = camera.stream_url.strip()

    if "://" not in stream_url:
        raise HTTPException(
            status_code=400,
            detail="Camera stream URL must include a protocol such as rtsp:// or http://"
        )

    protocol = stream_url.split("://", 1)[0].lower()

    supported_protocols = {
        "rtsp",
        "http",
        "https"
    }

    if protocol not in supported_protocols:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported camera protocol: {protocol}"
        )

    return stream_url


# ============================================================
# MediaMTX Status
# ============================================================

def get_mediamtx_status():

    try:

        response = requests.get(
            f"{MEDIAMTX_API}/v3/paths/list",
            auth=(
                MEDIAMTX_USERNAME,
                MEDIAMTX_PASSWORD
            ),
            timeout=3
        )

        response.raise_for_status()

        return response.json().get("items", [])

    except requests.RequestException as error:

        print(
            f"[MediaMTX] API error: {error}"
        )

        return None


# ============================================================
# Root
# ============================================================

@app.get("/")
def root():

    return {
        "service": "AI CCTV Platform",
        "status": "running",
        "version": "0.2.0",
        "docs": "/docs",
        "health": "/health"
    }


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "AI CCTV Platform",
        "version": "0.2.0"
    }


# ============================================================
# Get All Cameras
# ============================================================

@app.get("/api/cameras")
def get_cameras():

    db: Session = get_db()

    try:

        cameras = db.query(Camera).all()

        return {
            "count": len(cameras),

            "cameras": [

                {
                    "id": camera.id,
                    "camera_id": camera.camera_id,
                    "name": camera.name,
                    "manufacturer": camera.manufacturer,
                    "protocol": camera.protocol,
                    "host": camera.host,
                    "port": camera.port,
                    "stream_url": camera.stream_url
                }

                for camera in cameras
            ]
        }

    finally:

        db.close()


# ============================================================
# Get Single Camera
# ============================================================

@app.get("/api/cameras/{camera_id}")
def get_camera(camera_id: str):

    db: Session = get_db()

    try:

        camera = (
            db.query(Camera)
            .filter(
                Camera.camera_id == camera_id
            )
            .first()
        )

        if not camera:

            raise HTTPException(
                status_code=404,
                detail="Camera not found"
            )

        return {
            "id": camera.id,
            "camera_id": camera.camera_id,
            "name": camera.name,
            "manufacturer": camera.manufacturer,
            "protocol": camera.protocol,
            "host": camera.host,
            "port": camera.port,
            "stream_url": camera.stream_url
        }

    finally:

        db.close()


# ============================================================
# Get Camera Status
# ============================================================

@app.get("/api/cameras/{camera_id}/status")
def get_camera_status(camera_id: str):

    db: Session = get_db()

    try:

        camera = (
            db.query(Camera)
            .filter(
                Camera.camera_id == camera_id
            )
            .first()
        )

        if not camera:

            raise HTTPException(
                status_code=404,
                detail="Camera not found"
            )

        paths = get_mediamtx_status()

        if paths is None:

            return {
                "camera_id": camera.camera_id,
                "status": "unknown",
                "online": False,
                "message": "MediaMTX is unavailable"
            }

        camera_path = next(
            (
                path
                for path in paths
                if path.get("name") == camera.camera_id
            ),
            None
        )

        if camera_path is None:

            return {
                "camera_id": camera.camera_id,
                "status": "offline",
                "online": False
            }

        online = camera_path.get(
            "online",
            False
        )

        return {
            "camera_id": camera.camera_id,
            "status": (
                "online"
                if online
                else "offline"
            ),
            "online": online
        }

    finally:

        db.close()


# ============================================================
# Get Camera Stream
# ============================================================

@app.get("/api/cameras/{camera_id}/stream")
def get_camera_stream(camera_id: str):

    db: Session = get_db()

    try:

        camera = (
            db.query(Camera)
            .filter(
                Camera.camera_id == camera_id
            )
            .first()
        )

        if not camera:

            raise HTTPException(
                status_code=404,
                detail="Camera not found"
            )

        paths = get_mediamtx_status()

        if paths is None:

            return {
                "camera_id": camera.camera_id,
                "status": "unknown",
                "online": False,
                "message": "MediaMTX is unavailable"
            }

        camera_path = next(
            (
                path
                for path in paths
                if path.get("name") == camera.camera_id
            ),
            None
        )

        if camera_path is None:

            return {
                "camera_id": camera.camera_id,
                "status": "offline",
                "online": False
            }

        online = camera_path.get(
            "online",
            False
        )

        if not online:

            return {
                "camera_id": camera.camera_id,
                "status": "offline",
                "online": False
            }

        return {
            "camera_id": camera.camera_id,
            "status": "online",
            "online": True,

            "streams": {

                "webrtc": (
                    f"http://127.0.0.1:8889/"
                    f"{camera.camera_id}/"
                ),

                "hls": (
                    f"http://127.0.0.1:8888/"
                    f"{camera.camera_id}/"
                )
            }
        }

    finally:

        db.close()


# ============================================================
# Register Camera
# ============================================================

@app.post("/api/cameras")
def create_camera(camera_data: CameraCreate):

    db: Session = get_db()

    try:

        existing_camera = (
            db.query(Camera)
            .filter(
                Camera.camera_id == camera_data.camera_id
            )
            .first()
        )

        if existing_camera:

            raise HTTPException(
                status_code=409,
                detail="Camera ID already exists"
            )

        protocol = camera_data.protocol.upper()

        supported_protocols = {
            "RTSP",
            "HTTP",
            "HTTPS"
        }

        if protocol not in supported_protocols:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Unsupported protocol. "
                    "Use RTSP, HTTP or HTTPS."
                )
            )

        if "://" not in camera_data.stream_url:

            raise HTTPException(
                status_code=400,
                detail="stream_url must include protocol"
            )

        actual_protocol = (
            camera_data.stream_url
            .split("://", 1)[0]
            .upper()
        )

        if actual_protocol != protocol:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Protocol mismatch: "
                    f"protocol={protocol}, "
                    f"stream_url={actual_protocol}"
                )
            )

        camera = Camera(
            camera_id=camera_data.camera_id,
            name=camera_data.name,
            manufacturer=camera_data.manufacturer,
            protocol=protocol,
            host=camera_data.host,
            port=camera_data.port,
            stream_url=camera_data.stream_url,
            username=camera_data.username,
            password=camera_data.password
        )

        db.add(camera)

        db.commit()

        db.refresh(camera)

        return {
            "message": "Camera registered successfully",

            "camera": {
                "id": camera.id,
                "camera_id": camera.camera_id,
                "name": camera.name,
                "manufacturer": camera.manufacturer,
                "protocol": camera.protocol,
                "host": camera.host,
                "port": camera.port,
                "stream_url": camera.stream_url
            }
        }

    finally:

        db.close()


# ============================================================
# Start Camera Stream
# ============================================================

@app.post("/api/cameras/{camera_id}/start")
def start_camera(camera_id: str):

    db: Session = get_db()

    try:

        camera = (
            db.query(Camera)
            .filter(
                Camera.camera_id == camera_id
            )
            .first()
        )

        if not camera:

            raise HTTPException(
                status_code=404,
                detail="Camera not found"
            )

        camera_url = build_camera_url(camera)

        started = stream_manager.start_camera(
            camera_id=camera.camera_id,
            camera_url=camera_url,
            username=camera.username,
            password=camera.password
        )

        if not started:

            raise HTTPException(
                status_code=500,
                detail="Failed to start camera stream"
            )

        return {
            "camera_id": camera.camera_id,
            "status": "starting",
            "message": "Camera stream started"
        }

    finally:

        db.close()


# ============================================================
# Stop Camera Stream
# ============================================================

@app.post("/api/cameras/{camera_id}/stop")
def stop_camera(camera_id: str):

    db: Session = get_db()

    try:

        camera = (
            db.query(Camera)
            .filter(
                Camera.camera_id == camera_id
            )
            .first()
        )

        if not camera:

            raise HTTPException(
                status_code=404,
                detail="Camera not found"
            )

        stopped = stream_manager.stop_camera(
            camera.camera_id
        )

        if not stopped:

            return {
                "camera_id": camera.camera_id,
                "status": "stopped",
                "message": "Camera was not running"
            }

        return {
            "camera_id": camera.camera_id,
            "status": "stopped",
            "message": "Camera stream stopped"
        }

    finally:

        db.close()