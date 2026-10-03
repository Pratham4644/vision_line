# import cv2
# import time
# import json
# import boto3

# RTSP_URL = "rtsp://127.0.0.1:8554/cam1"
# ENDPOINT_NAME = "yolo26s-cctv-endpoint"
# REGION = "us-east-1"

# sagemaker = boto3.client(
#     "sagemaker-runtime",
#     region_name=REGION
# )

# cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)

# if not cap.isOpened():
#     raise RuntimeError("Could not open cam1 RTSP stream")

# print("Connected to cam1")
# print("Starting 1 FPS SageMaker inference...")

# last_sample_time = 0
# sample_count = 0

# while True:
#     ret, frame = cap.read()

#     if not ret:
#         print("Failed to read frame")
#         break

#     now = time.time()

#     if now - last_sample_time >= 1.0:
#         last_sample_time = now
#         sample_count += 1

#         # Encode frame as JPEG
#         success, encoded = cv2.imencode(
#             ".jpg",
#             frame,
#             [cv2.IMWRITE_JPEG_QUALITY, 80]
#         )

#         if not success:
#             print(f"Sample #{sample_count}: JPEG encoding failed")
#             continue

#         jpeg_bytes = encoded.tobytes()

#         # Send frame to SageMaker
#         start = time.time()

#         response = sagemaker.invoke_endpoint(
#             EndpointName=ENDPOINT_NAME,
#             ContentType="image/jpeg",
#             Body=jpeg_bytes
#         )

#         inference_time = time.time() - start

#         result = json.loads(
#             response["Body"].read().decode("utf-8")
#         )

#         detections = result.get("detections", [])

#         print(
#             f"\nSample #{sample_count} | "
#             f"JPEG: {len(jpeg_bytes) / 1024:.1f} KB | "
#             f"AWS: {inference_time:.2f}s | "
#             f"Detections: {len(detections)}"
#         )

#         for detection in detections:
#             print(
#                 f"  {detection['class_name']} "
#                 f"{detection['confidence']:.2%} "
#                 f"bbox={detection['bbox']}"
#             )

# cap.release()


import cv2
import time
import json
import boto3
import threading
import subprocess


# ============================================================
# Configuration
# ============================================================

INPUT_RTSP_URL = "rtsp://127.0.0.1:8554/cam1"
OUTPUT_RTSP_URL = "rtsp://PS:Sasha123@127.0.0.1:8554/cam1-ai"

ENDPOINT_NAME = "yolo26s-cctv-endpoint"
REGION = "us-east-1"

INFERENCE_INTERVAL = 1.0
JPEG_QUALITY = 80


# ============================================================
# AWS SageMaker
# ============================================================

sagemaker = boto3.client(
    "sagemaker-runtime",
    region_name=REGION
)


# ============================================================
# Shared state
# ============================================================

latest_frame = None
latest_detections = []

frame_lock = threading.Lock()
detection_lock = threading.Lock()

stop_event = threading.Event()


# ============================================================
# SageMaker inference worker
# ============================================================

def inference_worker():

    global latest_frame
    global latest_detections

    sample_count = 0

    print("SageMaker worker started")

    while not stop_event.is_set():

        # Get newest frame
        with frame_lock:

            if latest_frame is None:
                frame = None
            else:
                frame = latest_frame.copy()

        if frame is None:

            time.sleep(0.05)
            continue

        sample_count += 1

        # Encode JPEG
        success, encoded = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
        )

        if not success:

            print("JPEG encoding failed")
            continue

        jpeg_bytes = encoded.tobytes()

        start = time.time()

        try:

            response = sagemaker.invoke_endpoint(
                EndpointName=ENDPOINT_NAME,
                ContentType="image/jpeg",
                Body=jpeg_bytes
            )

            inference_time = time.time() - start

            result = json.loads(
                response["Body"].read().decode("utf-8")
            )

            detections = result.get(
                "detections",
                []
            )

            with detection_lock:

                latest_detections = detections

            print(
                f"SageMaker #{sample_count} | "
                f"AWS: {inference_time:.2f}s | "
                f"Detections: {len(detections)}"
            )

        except Exception as e:

            print(
                f"SageMaker error: {e}"
            )

        elapsed = time.time() - start

        sleep_time = max(
            0,
            INFERENCE_INTERVAL - elapsed
        )

        time.sleep(sleep_time)


# ============================================================
# Open input RTSP stream
# ============================================================

cap = cv2.VideoCapture(
    INPUT_RTSP_URL,
    cv2.CAP_FFMPEG
)

if not cap.isOpened():

    raise RuntimeError(
        "Could not open cam1 RTSP stream"
    )


print("Connected to cam1")


# ============================================================
# Read video properties
# ============================================================

width = int(
    cap.get(cv2.CAP_PROP_FRAME_WIDTH)
)

height = int(
    cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
)

fps = cap.get(
    cv2.CAP_PROP_FPS
)

if fps <= 0 or fps > 60:

    fps = 15.0


print(
    f"Input video: {width}x{height} @ {fps:.2f} FPS"
)


# ============================================================
# Start FFmpeg publisher
# ============================================================

ffmpeg_command = [

    "ffmpeg",

    "-loglevel",
    "warning",

    # Raw frames coming from Python
    "-f",
    "rawvideo",

    "-pix_fmt",
    "bgr24",

    "-s",
    f"{width}x{height}",

    "-r",
    str(fps),

    "-i",
    "-",

    # H.264 encoding
    "-c:v",
    "libx264",

    "-preset",
    "ultrafast",

    "-tune",
    "zerolatency",

    "-pix_fmt",
    "yuv420p",

    "-g",
    str(int(fps)),

    "-f",
    "rtsp",

    "-rtsp_transport",
    "tcp",

    OUTPUT_RTSP_URL
]


print("Starting FFmpeg...")
print("Publishing processed stream to:")
print(OUTPUT_RTSP_URL)


ffmpeg_process = subprocess.Popen(
    ffmpeg_command,
    stdin=subprocess.PIPE
)


# ============================================================
# Start SageMaker worker
# ============================================================

worker = threading.Thread(
    target=inference_worker,
    daemon=True
)

worker.start()


print("Starting AI processed video...")


# ============================================================
# Main video loop
# ============================================================

try:

    while True:

        # ONLY this loop reads RTSP
        ret, frame = cap.read()

        if not ret:

            print(
                "Failed to read frame"
            )

            break


        # Share newest frame with SageMaker
        with frame_lock:

            latest_frame = frame.copy()


        # Get latest detections
        with detection_lock:

            detections = latest_detections.copy()


        # ====================================================
        # Draw detections
        # ====================================================

        for detection in detections:

            class_name = detection[
                "class_name"
            ]

            confidence = detection[
                "confidence"
            ]

            x1, y1, x2, y2 = map(
                int,
                detection["bbox"]
            )


            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2
            )


            label = (
                f"{class_name} "
                f"{confidence:.0%}"
            )


            cv2.putText(
                frame,
                label,
                (
                    x1,
                    max(30, y1 - 10)
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )


        # ====================================================
        # Send processed frame to FFmpeg
        # ====================================================

        try:

            ffmpeg_process.stdin.write(
                frame.tobytes()
            )

        except (BrokenPipeError, OSError):

            print(
                "FFmpeg publisher stopped"
            )

            break


        # ====================================================
        # Local preview
        # ====================================================

        cv2.imshow(
            "AI CCTV - cam1",
            frame
        )


        if cv2.waitKey(1) & 0xFF == ord("q"):

            break


finally:

    print("Stopping AI worker...")

    stop_event.set()

    cap.release()

    try:

        ffmpeg_process.stdin.close()

    except Exception:

        pass

    try:

        ffmpeg_process.wait(
            timeout=5
        )

    except subprocess.TimeoutExpired:

        ffmpeg_process.kill()


    cv2.destroyAllWindows()

    print("AI worker stopped")