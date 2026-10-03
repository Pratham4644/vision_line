import boto3
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ENDPOINT_NAME = "yolo26s-cctv-endpoint"
REGION = "us-east-1"
IMAGE_PATH = r"D:\pyy.intern\images.jpg"

CAMERA_COUNT = 12
FPS_PER_CAMERA = 1
TEST_DURATION = 30

runtime = boto3.client(
    "sagemaker-runtime",
    region_name=REGION
)

with open(IMAGE_PATH, "rb") as f:
    image_bytes = f.read()


def infer(camera_id, frame_number):
    start = time.perf_counter()

    try:
        response = runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType="image/jpeg",
            Body=image_bytes
        )

        elapsed = time.perf_counter() - start

        body = response["Body"].read()
        result = json.loads(body)

        return {
            "camera": camera_id,
            "frame": frame_number,
            "success": True,
            "latency": elapsed,
            "detections": len(result.get("detections", []))
        }

    except Exception as e:
        elapsed = time.perf_counter() - start

        return {
            "camera": camera_id,
            "frame": frame_number,
            "success": False,
            "latency": elapsed,
            "error": str(e)
        }


executor = ThreadPoolExecutor(max_workers=CAMERA_COUNT)

futures = []

start_time = time.perf_counter()
next_second = start_time
frame_number = 0

print()
print("=" * 70)
print("12-CAMERA SUSTAINED LOAD TEST")
print("=" * 70)
print(f"Cameras          : {CAMERA_COUNT}")
print(f"FPS per camera   : {FPS_PER_CAMERA}")
print(f"Target requests/s: {CAMERA_COUNT * FPS_PER_CAMERA}")
print(f"Duration         : {TEST_DURATION}s")
print(f"Endpoint         : {ENDPOINT_NAME}")
print("=" * 70)

while time.perf_counter() - start_time < TEST_DURATION:

    now = time.perf_counter()

    if now >= next_second:
        frame_number += 1

        for camera_id in range(1, CAMERA_COUNT + 1):
            futures.append(
                executor.submit(
                    infer,
                    camera_id,
                    frame_number
                )
            )

        print(
            f"Sent batch {frame_number:02d} "
            f"({CAMERA_COUNT} requests)"
        )

        next_second += 1.0

    time.sleep(0.01)


print()
print("Waiting for outstanding requests...")
print()

results = []

for future in as_completed(futures):
    results.append(future.result())

executor.shutdown()

total_time = time.perf_counter() - start_time

successful = [
    r for r in results
    if r["success"]
]

failed = [
    r for r in results
    if not r["success"]
]

print("=" * 70)
print("FINAL RESULTS")
print("=" * 70)

print(f"Test duration          : {TEST_DURATION}s")
print(f"Actual elapsed time    : {total_time:.2f}s")
print(f"Requests sent          : {len(results)}")
print(f"Successful             : {len(successful)}")
print(f"Failed                 : {len(failed)}")

if results:
    print(
        f"Completed throughput  : "
        f"{len(results) / total_time:.2f} req/s"
    )

if successful:

    latencies = [
        r["latency"]
        for r in successful
    ]

    print()
    print("Latency")
    print("-" * 70)
    print(f"Average                : {sum(latencies)/len(latencies):.3f}s")
    print(f"Minimum                : {min(latencies):.3f}s")
    print(f"Maximum                : {max(latencies):.3f}s")

if failed:

    print()
    print("Failures")
    print("-" * 70)

    for result in failed[:10]:
        print(
            f"Camera {result['camera']:02d} | "
            f"Frame {result['frame']:02d} | "
            f"{result['error']}"
        )

print()
print("=" * 70)