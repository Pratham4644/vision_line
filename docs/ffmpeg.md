# FFmpeg Ingestion Engine

## 1. Overview
The backend `FFmpegService` acts as an edge ingest supervisor. It launches, monitors, health-checks, and restarts isolated FFmpeg worker processes for every active camera stream.

## 2. Ingestion Commands
### H.264 Passthrough (Default for RTSP Cameras)
```bash
ffmpeg -hide_banner -loglevel warning \
  -fflags nobuffer -flags low_delay \
  -rtsp_transport tcp -stimeout 5000000 \
  -i "rtsp://username:password@192.168.1.50:554/h264" \
  -an -c:v copy \
  -f rtsp -rtsp_transport tcp "rtsp://127.0.0.1:8554/cam-test-1"
```
**Why this works**:
- CPU consumption is near zero (~1–2% CPU per stream).
- No re-encoding latency.
- Memory consumption per worker is less than 20 MB.

### MJPEG / HTTP Transcode (For Legacy Sources / Mobile Streams)
```bash
ffmpeg -hide_banner -loglevel warning \
  -fflags nobuffer -flags low_delay \
  -i "http://192.168.1.50:8080/video" \
  -an -r 15 -c:v libx264 -preset ultrafast -tune zerolatency \
  -b:v 800k -pix_fmt yuv420p \
  -f rtsp -rtsp_transport tcp "rtsp://127.0.0.1:8554/cam-mjpeg"
```

## 3. Crash Detection and Auto-Reconnect
Each worker monitors its FFmpeg process output asynchronously. If the camera source drops or network disconnects:
1. The process exit code is captured and logged.
2. The Stream state in MongoDB transitions to `DEGRADED` or `OFFLINE`.
3. An exponential backoff sleep (1s, 2s, 4s, up to 30s max) occurs.
4. FFmpeg automatically relaunches and restores the stream once the camera is reachable again.
5. An audit log `STREAM_RECONNECTED` event is recorded.
