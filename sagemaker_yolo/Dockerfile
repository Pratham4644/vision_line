FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    torch==2.6.0+cpu \
    torchvision==0.21.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .

RUN pip install --no-cache-dir --no-deps ultralytics \
    && pip install --no-cache-dir \
    flask \
    pillow \
    numpy \
    requests \
    pyyaml \
    matplotlib \
    opencv-python-headless \
    polars \
    psutil \
    ultralytics-thop

RUN mkdir -p /opt/ml/model

COPY yolo26s.pt /opt/ml/model/yolo26s.pt
COPY inference.py /app/inference.py

EXPOSE 8080

ENTRYPOINT ["python", "/app/inference.py"]
