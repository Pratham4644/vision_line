# import time
# import base64
# from urllib.request import Request, urlopen

# import cv2
# import numpy as np

# from fastapi import FastAPI
# from fastapi.responses import HTMLResponse, StreamingResponse


# # ============================================================
# # FASTAPI APP
# # ============================================================

# app = FastAPI(title="CCTV Streaming Server")


# # ============================================================
# # CAMERA CONFIGURATION
# # ============================================================

# CAMERA_IP = "192.168.1.4"
# CAMERA_PORT = 8080

# CAMERA_USERNAME = "hello"
# CAMERA_PASSWORD = "Pratham@123"

# CAMERA_URL = f"http://{CAMERA_IP}:{CAMERA_PORT}/video"


# # ============================================================
# # BASIC AUTHENTICATION
# # ============================================================

# def get_auth_header():
#     """
#     Create HTTP Basic Authentication header.

#     Equivalent to:

#         curl -u "hello:password"
#     """

#     credentials = f"{CAMERA_USERNAME}:{CAMERA_PASSWORD}"

#     encoded_credentials = base64.b64encode(
#         credentials.encode("utf-8")
#     ).decode("ascii")

#     return f"Basic {encoded_credentials}"


# # ============================================================
# # CAMERA FRAME GENERATOR
# # ============================================================

# def camera_frames():

#     while True:

#         try:

#             print(
#                 f"Connecting to camera: "
#                 f"{CAMERA_IP}:{CAMERA_PORT}/video"
#             )

#             # ------------------------------------------------
#             # Create HTTP request
#             # ------------------------------------------------

#             request = Request(
#                 CAMERA_URL,
#                 headers={
#                     "Authorization": get_auth_header(),
#                     "User-Agent": "Mozilla/5.0",
#                     "Cache-Control": "no-cache",
#                 },
#             )

#             # ------------------------------------------------
#             # Connect to camera
#             # ------------------------------------------------

#             with urlopen(
#                 request,
#                 timeout=10
#             ) as stream:

#                 print("Camera connected!")

#                 buffer = b""

#                 # ============================================
#                 # READ MJPEG STREAM
#                 # ============================================

#                 while True:

#                     chunk = stream.read(8192)

#                     if not chunk:
#                         print("Camera stream ended.")
#                         break

#                     buffer += chunk

#                     # ----------------------------------------
#                     # Find JPEG START
#                     # JPEG starts with FF D8
#                     # ----------------------------------------

#                     start = buffer.find(
#                         b"\xff\xd8"
#                     )

#                     if start == -1:
#                         continue

#                     # ----------------------------------------
#                     # Find JPEG END
#                     # JPEG ends with FF D9
#                     # ----------------------------------------

#                     end = buffer.find(
#                         b"\xff\xd9",
#                         start + 2
#                     )

#                     if end == -1:
#                         continue

#                     end += 2

#                     # ----------------------------------------
#                     # Extract complete JPEG
#                     # ----------------------------------------

#                     jpeg = buffer[start:end]

#                     buffer = buffer[end:]

#                     # ----------------------------------------
#                     # JPEG -> NumPy
#                     # ----------------------------------------

#                     frame_array = np.frombuffer(
#                         jpeg,
#                         dtype=np.uint8
#                     )

#                     # ----------------------------------------
#                     # NumPy -> OpenCV frame
#                     # ----------------------------------------

#                     frame = cv2.imdecode(
#                         frame_array,
#                         cv2.IMREAD_COLOR
#                     )

#                     if frame is None:
#                         continue

#                     # ----------------------------------------
#                     # Return OpenCV frame
#                     # ----------------------------------------

#                     yield frame

#         except Exception as error:

#             print(
#                 f"Camera connection error: {error}"
#             )

#             print("Retrying in 2 seconds...")

#             time.sleep(2)


# # ============================================================
# # PROCESS FRAME + CREATE OUTPUT STREAM
# # ============================================================

# def generate():

#     for frame in camera_frames():

#         # ====================================================
#         # AI / COMPUTER VISION PROCESSING WILL GO HERE
#         # ====================================================

#         # Later we will add YOLO here.
#         #
#         # Example:
#         #
#         # results = model(frame)
#         # frame = results[0].plot()
#         #
#         # ====================================================


#         # ====================================================
#         # OPENCV FRAME -> JPEG
#         # ====================================================

#         success, encoded = cv2.imencode(
#             ".jpg",
#             frame,
#             [
#                 cv2.IMWRITE_JPEG_QUALITY,
#                 80
#             ],
#         )

#         if not success:
#             continue

#         frame_bytes = encoded.tobytes()


#         # ====================================================
#         # SEND MJPEG FRAME
#         # ====================================================

#         yield (
#             b"--frame\r\n"
#             b"Content-Type: image/jpeg\r\n"
#             b"Content-Length: "
#             + str(len(frame_bytes)).encode()
#             + b"\r\n\r\n"
#             + frame_bytes
#             + b"\r\n"
#         )


# # ============================================================
# # VIDEO ENDPOINT
# # ============================================================

# @app.get("/video")
# def video():

#     return StreamingResponse(
#         generate(),
#         media_type="multipart/x-mixed-replace; boundary=frame",
#         headers={
#             "Cache-Control": "no-cache",
#             "Pragma": "no-cache",
#         },
#     )


# # ============================================================
# # HOME PAGE
# # ============================================================

# @app.get(
#     "/",
#     response_class=HTMLResponse
# )
# def home():

#     return """
#     <!DOCTYPE html>

#     <html>

#     <head>

#         <meta charset="UTF-8">

#         <title>CCTV Live Feed</title>

#         <style>

#             * {
#                 box-sizing: border-box;
#             }

#             body {

#                 margin: 0;

#                 background: #111;

#                 color: white;

#                 font-family: Arial, sans-serif;

#                 text-align: center;
#             }

#             h1 {

#                 margin: 20px 0;

#             }

#             .status {

#                 margin-bottom: 20px;

#                 color: #00ff88;

#             }

#             .camera {

#                 display: inline-block;

#                 background: #222;

#                 padding: 15px;

#                 border-radius: 12px;

#                 box-shadow:
#                     0 0 20px
#                     rgba(0, 0, 0, 0.5);
#             }

#             img {

#                 display: block;

#                 width: 800px;

#                 max-width: 90vw;

#                 height: auto;

#                 border-radius: 8px;
#             }

#         </style>

#     </head>


#     <body>

#         <h1>
#             CCTV Live Feed
#         </h1>

#         <div class="status">
#             ● LIVE
#         </div>

#         <div class="camera">

#             <img
#                 src="/video"
#                 alt="CCTV Live Feed"
#             >

#         </div>

#     </body>

#     </html>
#     """


# # ============================================================
# # HEALTH CHECK
# # ============================================================

# @app.get("/health")
# def health():

#     return {

#         "status": "ok",

#         "camera":
#             f"{CAMERA_IP}:{CAMERA_PORT}",

#         "camera_url":
#             CAMERA_URL,

#         "stream":
#             "/video"

#     }


# # ============================================================
# # RUN DIRECTLY WITH PYTHON
# # ============================================================

# if __name__ == "__main__":

#     import uvicorn

#     uvicorn.run(
#         app,
#         host="0.0.0.0",
#         port=8001
#     )






## for now we are removing the opencv  just making a simple streaming server with fastapi and uvicorn


# import time
# import base64
# from urllib.request import Request, urlopen

# from fastapi import FastAPI
# from fastapi.responses import HTMLResponse, StreamingResponse

# app = FastAPI(title="CCTV Streaming Server")

# CAMERA_IP = "192.168.1.9"
# CAMERA_PORT = 8080

# CAMERA_USERNAME = "hello"
# CAMERA_PASSWORD = "Pratham@123"

# CAMERA_URL = f"http://{CAMERA_IP}:{CAMERA_PORT}/video"


# def get_auth_header():

#     credentials = f"{CAMERA_USERNAME}:{CAMERA_PASSWORD}"

#     encoded = base64.b64encode(
#         credentials.encode("utf-8")
#     ).decode("ascii")

#     return f"Basic {encoded}"


# def stream_camera():

#     while True:

#         try:

#             print("Connecting to camera...")

#             request = Request(
#                 CAMERA_URL,
#                 headers={
#                     "Authorization": get_auth_header(),
#                     "User-Agent": "Mozilla/5.0",
#                     "Cache-Control": "no-cache",
#                 },
#             )

#             with urlopen(request, timeout=10) as camera:

#                 print("Camera connected!")

#                 # IMPORTANT:
#                 # Get the camera's REAL Content-Type
#                 content_type = camera.headers.get("Content-Type")

#                 print("Camera Content-Type:", content_type)

#                 while True:

#                     chunk = camera.read(16384)

#                     if not chunk:
#                         print("Camera stream ended")
#                         break

#                     yield chunk

#         except Exception as error:

#             print("Camera error:", error)

#             time.sleep(1)


# @app.get("/video")
# def video():

#     # Connect once so we can obtain the camera's
#     # original Content-Type / boundary.

#     try:

#         request = Request(
#             CAMERA_URL,
#             headers={
#                 "Authorization": get_auth_header(),
#                 "User-Agent": "Mozilla/5.0",
#                 "Cache-Control": "no-cache",
#             },
#         )

#         camera = urlopen(request, timeout=10)

#         content_type = camera.headers.get("Content-Type")

#         print("Camera Content-Type:", content_type)

#         def generate():

#             try:

#                 while True:

#                     chunk = camera.read(16384)

#                     if not chunk:
#                         break

#                     yield chunk

#             except Exception as error:

#                 print("Stream error:", error)

#             finally:

#                 camera.close()

#         return StreamingResponse(
#             generate(),

#             # DO NOT change the camera boundary
#             media_type=None,

#             headers={
#                 "Content-Type": content_type,
#                 "Cache-Control": "no-cache, no-store, must-revalidate",
#                 "Pragma": "no-cache",
#                 "Expires": "0",
#                 "X-Accel-Buffering": "no",
#             },
#         )

#     except Exception as error:

#         print("Camera connection failed:", error)

#         return {
#             "error": str(error)
#         }


# @app.get("/", response_class=HTMLResponse)
# def home():

#     return """
#     <!DOCTYPE html>

#     <html>

#     <head>

#         <meta charset="UTF-8">

#         <meta name="viewport"
#               content="width=device-width, initial-scale=1.0">

#         <title>CCTV Live Feed</title>

#         <style>

#             body {
#                 margin: 0;
#                 background: #111;
#                 color: white;
#                 font-family: Arial;
#                 text-align: center;
#             }

#             h1 {
#                 margin: 20px;
#             }

#             .status {
#                 color: #00ff88;
#                 margin-bottom: 15px;
#             }

#             img {
#                 width: 800px;
#                 max-width: 95vw;
#                 border-radius: 8px;
#             }

#         </style>

#     </head>

#     <body>

#         <h1>CCTV Live Feed</h1>

#         <div class="status">
#             ● LIVE
#         </div>

#         <img src="/video">

#     </body>

#     </html>
#     """


# @app.get("/health")
# def health():

#     return {
#         "status": "ok",
#         "camera": f"{CAMERA_IP}:{CAMERA_PORT}",
#         "stream": "/video"
#     }


# if __name__ == "__main__":

#     import uvicorn

#     uvicorn.run(
#         app,
#         host="0.0.0.0",
#         port=8001
#     )


# from fastapi import FastAPI, HTTPException


# app = FastAPI(
#     title="AI CCTV Platform",
#     version="0.1.0"
# )


# # ============================================================
# # CAMERA REGISTRY
# # ============================================================

# CAMERAS = {

#     "cam1": {
#         "id": "cam1",
#         "name": "Development Camera",
#         "status": "online",

#         "streams": {
#             "webrtc": "http://127.0.0.1:8889/cam1/",
#             "hls": "http://127.0.0.1:8888/cam1/index.m3u8",
#             "rtsp": "rtsp://127.0.0.1:8554/cam1"
#         },

#         "ai": {
#             "enabled": False,
#             "models": []
#         }
#     }

# }


# # ============================================================
# # HEALTH
# # ============================================================

# @app.get("/health")
# def health():

#     return {
#         "status": "ok",
#         "service": "AI CCTV Platform",
#         "version": "0.1.0"
#     }


# # ============================================================
# # GET ALL CAMERAS
# # ============================================================

# @app.get("/api/cameras")
# def get_cameras():

#     return {
#         "count": len(CAMERAS),
#         "cameras": list(CAMERAS.values())
#     }


# # ============================================================
# # GET ONE CAMERA
# # ============================================================

# @app.get("/api/cameras/{camera_id}")
# def get_camera(camera_id: str):

#     camera = CAMERAS.get(camera_id)

#     if camera is None:
#         raise HTTPException(
#             status_code=404,
#             detail="Camera not found"
#         )

#     return camera


# # ============================================================
# # GET CAMERA STREAMS
# # ============================================================

# @app.get("/api/cameras/{camera_id}/stream")
# def get_camera_stream(camera_id: str):

#     camera = CAMERAS.get(camera_id)

#     if camera is None:
#         raise HTTPException(
#             status_code=404,
#             detail="Camera not found"
#         )

#     return {
#         "camera_id": camera_id,
#         "streams": camera["streams"]
#     }


# # ============================================================
# # ROOT
# # ============================================================

# @app.get("/")
# def root():

#     return {
#         "service": "AI CCTV Platform",
#         "status": "running",
#         "docs": "/docs",
#         "health": "/health"
#     }
import requests

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Camera


app = FastAPI(
    title="AI CCTV Platform",
    version="0.1.0"
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
    host: str
    port: int | None = None
    username: str | None = None
    password: str | None = None


# ============================================================
# MediaMTX Configuration
# ============================================================

MEDIAMTX_API = "http://127.0.0.1:9997"

MEDIAMTX_USERNAME = "PS"

# Put your actual MediaMTX password here locally.
# Do NOT paste the password into chat.
MEDIAMTX_PASSWORD = "Sangola@123"


# ============================================================
# Database
# ============================================================

def get_db():
    return SessionLocal()


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

        print(f"MediaMTX API error: {error}")

        return None


# ============================================================
# Root
# ============================================================

@app.get("/")
def root():

    return {
        "service": "AI CCTV Platform",
        "status": "running",
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
        "version": "0.1.0"
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
                    "port": camera.port
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
            "port": camera.port
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

        # ----------------------------------------------------
        # Check database
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Query MediaMTX
        # ----------------------------------------------------

        paths = get_mediamtx_status()

        if paths is None:

            return {
                "camera_id": camera.camera_id,
                "status": "unknown",
                "online": False,
                "message": "MediaMTX is unavailable"
            }

        # ----------------------------------------------------
        # Find camera path
        # ----------------------------------------------------

        camera_path = None

        for path in paths:

            if path.get("name") == camera.camera_id:

                camera_path = path

                break

        # ----------------------------------------------------
        # Camera path not found
        # ----------------------------------------------------

        if camera_path is None:

            return {
                "camera_id": camera.camera_id,
                "status": "offline",
                "online": False
            }

        # ----------------------------------------------------
        # Get MediaMTX online state
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Check database
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Query MediaMTX
        # ----------------------------------------------------

        paths = get_mediamtx_status()

        if paths is None:

            return {
                "camera_id": camera.camera_id,
                "status": "unknown",
                "online": False,
                "message": "MediaMTX is unavailable"
            }

        # ----------------------------------------------------
        # Find camera path
        # ----------------------------------------------------

        camera_path = next(
            (
                path
                for path in paths
                if path.get("name")
                == camera.camera_id
            ),
            None
        )

        # ----------------------------------------------------
        # Camera path does not exist
        # ----------------------------------------------------

        if camera_path is None:

            return {
                "camera_id": camera.camera_id,
                "status": "offline",
                "online": False
            }

        # ----------------------------------------------------
        # Check online status
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Return stream information
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Check duplicate camera ID
        # ----------------------------------------------------

        existing_camera = (
            db.query(Camera)
            .filter(
                Camera.camera_id
                == camera_data.camera_id
            )
            .first()
        )

        if existing_camera:

            raise HTTPException(
                status_code=409,
                detail="Camera ID already exists"
            )

        # ----------------------------------------------------
        # Create camera
        # ----------------------------------------------------

        camera = Camera(

            camera_id=camera_data.camera_id,

            name=camera_data.name,

            manufacturer=camera_data.manufacturer,

            protocol=camera_data.protocol,

            host=camera_data.host,

            port=camera_data.port,

            username=camera_data.username,

            password=camera_data.password
        )

        # ----------------------------------------------------
        # Save
        # ----------------------------------------------------

        db.add(camera)

        db.commit()

        db.refresh(camera)

        # ----------------------------------------------------
        # Never return credentials
        # ----------------------------------------------------

        return {

            "message":
                "Camera registered successfully",

            "camera": {

                "id": camera.id,

                "camera_id":
                    camera.camera_id,

                "name":
                    camera.name,

                "manufacturer":
                    camera.manufacturer,

                "protocol":
                    camera.protocol,

                "host":
                    camera.host,

                "port":
                    camera.port
            }
        }

    finally:

        db.close()