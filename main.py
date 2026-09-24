import time
import base64
from urllib.request import Request, urlopen

import cv2
import numpy as np

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(title="CCTV Streaming Server")


# ============================================================
# CAMERA CONFIGURATION
# ============================================================

CAMERA_IP = "192.168.1.4"
CAMERA_PORT = 8080

CAMERA_USERNAME = "hello"
CAMERA_PASSWORD = "Pratham@123"

CAMERA_URL = f"http://{CAMERA_IP}:{CAMERA_PORT}/video"


# ============================================================
# BASIC AUTHENTICATION
# ============================================================

def get_auth_header():
    """
    Create HTTP Basic Authentication header.

    Equivalent to:

        curl -u "hello:password"
    """

    credentials = f"{CAMERA_USERNAME}:{CAMERA_PASSWORD}"

    encoded_credentials = base64.b64encode(
        credentials.encode("utf-8")
    ).decode("ascii")

    return f"Basic {encoded_credentials}"


# ============================================================
# CAMERA FRAME GENERATOR
# ============================================================

def camera_frames():

    while True:

        try:

            print(
                f"Connecting to camera: "
                f"{CAMERA_IP}:{CAMERA_PORT}/video"
            )

            # ------------------------------------------------
            # Create HTTP request
            # ------------------------------------------------

            request = Request(
                CAMERA_URL,
                headers={
                    "Authorization": get_auth_header(),
                    "User-Agent": "Mozilla/5.0",
                    "Cache-Control": "no-cache",
                },
            )

            # ------------------------------------------------
            # Connect to camera
            # ------------------------------------------------

            with urlopen(
                request,
                timeout=10
            ) as stream:

                print("Camera connected!")

                buffer = b""

                # ============================================
                # READ MJPEG STREAM
                # ============================================

                while True:

                    chunk = stream.read(8192)

                    if not chunk:
                        print("Camera stream ended.")
                        break

                    buffer += chunk

                    # ----------------------------------------
                    # Find JPEG START
                    # JPEG starts with FF D8
                    # ----------------------------------------

                    start = buffer.find(
                        b"\xff\xd8"
                    )

                    if start == -1:
                        continue

                    # ----------------------------------------
                    # Find JPEG END
                    # JPEG ends with FF D9
                    # ----------------------------------------

                    end = buffer.find(
                        b"\xff\xd9",
                        start + 2
                    )

                    if end == -1:
                        continue

                    end += 2

                    # ----------------------------------------
                    # Extract complete JPEG
                    # ----------------------------------------

                    jpeg = buffer[start:end]

                    buffer = buffer[end:]

                    # ----------------------------------------
                    # JPEG -> NumPy
                    # ----------------------------------------

                    frame_array = np.frombuffer(
                        jpeg,
                        dtype=np.uint8
                    )

                    # ----------------------------------------
                    # NumPy -> OpenCV frame
                    # ----------------------------------------

                    frame = cv2.imdecode(
                        frame_array,
                        cv2.IMREAD_COLOR
                    )

                    if frame is None:
                        continue

                    # ----------------------------------------
                    # Return OpenCV frame
                    # ----------------------------------------

                    yield frame

        except Exception as error:

            print(
                f"Camera connection error: {error}"
            )

            print("Retrying in 2 seconds...")

            time.sleep(2)


# ============================================================
# PROCESS FRAME + CREATE OUTPUT STREAM
# ============================================================

def generate():

    for frame in camera_frames():

        # ====================================================
        # AI / COMPUTER VISION PROCESSING WILL GO HERE
        # ====================================================

        # Later we will add YOLO here.
        #
        # Example:
        #
        # results = model(frame)
        # frame = results[0].plot()
        #
        # ====================================================


        # ====================================================
        # OPENCV FRAME -> JPEG
        # ====================================================

        success, encoded = cv2.imencode(
            ".jpg",
            frame,
            [
                cv2.IMWRITE_JPEG_QUALITY,
                80
            ],
        )

        if not success:
            continue

        frame_bytes = encoded.tobytes()


        # ====================================================
        # SEND MJPEG FRAME
        # ====================================================

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            b"Content-Length: "
            + str(len(frame_bytes)).encode()
            + b"\r\n\r\n"
            + frame_bytes
            + b"\r\n"
        )


# ============================================================
# VIDEO ENDPOINT
# ============================================================

@app.get("/video")
def video():

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )


# ============================================================
# HOME PAGE
# ============================================================

@app.get(
    "/",
    response_class=HTMLResponse
)
def home():

    return """
    <!DOCTYPE html>

    <html>

    <head>

        <meta charset="UTF-8">

        <title>CCTV Live Feed</title>

        <style>

            * {
                box-sizing: border-box;
            }

            body {

                margin: 0;

                background: #111;

                color: white;

                font-family: Arial, sans-serif;

                text-align: center;
            }

            h1 {

                margin: 20px 0;

            }

            .status {

                margin-bottom: 20px;

                color: #00ff88;

            }

            .camera {

                display: inline-block;

                background: #222;

                padding: 15px;

                border-radius: 12px;

                box-shadow:
                    0 0 20px
                    rgba(0, 0, 0, 0.5);
            }

            img {

                display: block;

                width: 800px;

                max-width: 90vw;

                height: auto;

                border-radius: 8px;
            }

        </style>

    </head>


    <body>

        <h1>
            CCTV Live Feed
        </h1>

        <div class="status">
            ● LIVE
        </div>

        <div class="camera">

            <img
                src="/video"
                alt="CCTV Live Feed"
            >

        </div>

    </body>

    </html>
    """


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {

        "status": "ok",

        "camera":
            f"{CAMERA_IP}:{CAMERA_PORT}",

        "camera_url":
            CAMERA_URL,

        "stream":
            "/video"

    }


# ============================================================
# RUN DIRECTLY WITH PYTHON
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001
    )