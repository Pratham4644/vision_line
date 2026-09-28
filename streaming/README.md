# MediaMTX 1.21.1 Media Plane

This directory contains the canonical MediaMTX configuration and runner for the multi-camera streaming platform.

## Architecture

- **Version**: Exactly `MediaMTX v1.21.1`
- **Control Plane**: FastAPI manages metadata, credentials encryption, RBAC, and stream state.
- **Media Plane**: MediaMTX distributes live video streams via RTSP and WebRTC (WHEP).
- **Ingest Plane**: Edge Gateways publish directly to MediaMTX over authenticated TCP RTSP.

```
Remote Camera -> Edge FFmpeg Gateway -> Authenticated RTSP/TCP -> MediaMTX 1.21.1 -> Authenticated WHEP/WebRTC -> Browser
```

## Role Separation & Authentication

MediaMTX strictly separates publisher and reader accounts using internal authentication (`authMethod: internal`):

1. **Publisher Account** (`MEDIAMTX_PUBLISH_USERNAME` / `MEDIAMTX_PUBLISH_PASSWORD`):
   - Action: `publish`
   - Path: `~^[a-zA-Z0-9_-]+$`
   - Reader action is explicitly forbidden.
2. **Reader Account** (`MEDIAMTX_READ_USERNAME` / `MEDIAMTX_READ_PASSWORD`):
   - Action: `read`
   - Path: `~^[a-zA-Z0-9_-]+$`
   - Publisher action is explicitly forbidden.
3. **Internal Monitor Account**:
   - Action: `api`, `metrics`
   - Restricted to `127.0.0.1` and `::1`.

Universal accounts (`user: any`) are strictly prohibited.

## Network Ports

| Protocol | Port | Transport | Purpose | Exposure |
|---|---|---|---|---|
| RTSP Ingest | 8554 | TCP | Edge FFmpeg stream ingestion | Edge Gateways / Public Azure NSG |
| WebRTC Signaling | 8889 | TCP | WHEP HTTP SDP handshake & ICE trickle | Nginx reverse proxy (Port 443) / Direct |
| WebRTC Media | 8189 | UDP | Direct P2P ICE media packets | Public Azure NSG |
| Control API | 9997 | TCP | Health & stream readiness probes | Localhost only (`127.0.0.1`) |
| Metrics | 9998 | TCP | Prometheus operational telemetry | Localhost only (`127.0.0.1`) |

## Running MediaMTX

### 1. Validate Configuration
```bash
mediamtx --validate-conf=streaming/mediamtx.yml
```

### 2. Start Service via Environment Runner
```bash
export MEDIAMTX_PUBLISH_USERNAME="edge_publisher"
export MEDIAMTX_PUBLISH_PASSWORD="<secure_publisher_password>"
export MEDIAMTX_READ_USERNAME="webrtc_reader"
export MEDIAMTX_READ_PASSWORD="<secure_reader_password>"

python streaming/run_mediamtx.py
```

### 3. Systemd Deployment
Install the unit file `deploy/systemd/mediamtx.service` on the server:
```bash
sudo cp deploy/systemd/mediamtx.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx
```

## Security & Path Traversal Rejection

Path regex strictly restricts path names to `^[a-zA-Z0-9_-]+$`. Any attempts at directory traversal (`../camera`), command injection (`camera;rm`), or illegal characters are rejected at the media server with `400 Bad Request` or `404 Not Found`.
