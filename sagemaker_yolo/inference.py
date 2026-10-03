from flask import Flask, request, jsonify
from ultralytics import YOLO
from PIL import Image
import io

app = Flask(__name__)

MODEL_PATH = "/opt/ml/model/yolo26s.pt"

model = YOLO(MODEL_PATH)


@app.get("/ping")
def ping():
    return "OK", 200


@app.post("/invocations")
def invocations():
    try:
        image_bytes = request.data

        if not image_bytes:
            return jsonify({"error": "Empty request body"}), 400

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        results = model.predict(
            source=image,
            conf=0.25,
            verbose=False
        )

        detections = []

        for result in results:
            for box in result.boxes:
                detections.append({
                    "class_id": int(box.cls[0]),
                    "class_name": result.names[int(box.cls[0])],
                    "confidence": float(box.conf[0]),
                    "bbox": [float(x) for x in box.xyxy[0].tolist()]
                })

        return jsonify({
            "detections": detections
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8080
    )