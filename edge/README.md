# Edge FFmpeg Ingest Gateway

The Edge Ingest Gateway (`edge/ingest.py`) runs at remote customer sites to ingest private camera RTSP streams and publish them securely to the central MediaMTX streaming server.

## Architecture

- **Scope**: Ingestion & transport only. Zero business logic, zero database queries, zero user auth.
- **Protocol**: RTSP over TCP (`-rtsp_transport tcp`).
- **Codec**: Passthrough H.264 copy (`-c:v copy -an`). No CPU-intensive transcoding.
- **Safety**: Subprocess execution via array args; strictly no `shell=True`.

```
IP Camera (192.168.x.x) ---> Edge FFmpeg Gateway ---> Authenticated RTSP/TCP ---> Azure MediaMTX
```

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `EDGE_CAMERA_ID` | Internal camera identifier | `cam-site1-01` |
| `EDGE_SOURCE_URL` | Local RTSP stream URL from camera | `rtsp://admin:pass@192.168.1.100:554/h264` |
| `EDGE_MEDIA_PATH` | Authorized media path on MediaMTX | `site1-cam01` |
| `MEDIAMTX_HOST` | Hostname or IP of Azure MediaMTX | `camera1.koreacentral.cloudapp.azure.com` |
| `MEDIAMTX_RTSP_PORT`| RTSP ingest port | `8554` |
| `MEDIAMTX_PUBLISH_USERNAME` | MediaMTX publisher username | `edge_publisher` |
| `MEDIAMTX_PUBLISH_PASSWORD` | MediaMTX publisher password | `<secret>` |

## Reconnection & Resilience

1. **Subprocess Supervision**: FFmpeg process is monitored continuously.
2. **Bounded Exponential Backoff**: When FFmpeg exits or camera disconnects, retries follow:
   - Initial delay: 2 seconds
   - Multiplier: 2x
   - Progression: 2s -> 4s -> 8s -> 16s -> 30s max
3. **Recovery Reset**: If a stream stays active for > 60 seconds, the backoff delay resets back to 2 seconds.
4. **Signal Handling**: Handles `SIGINT` and `SIGTERM` cleanly, ensuring FFmpeg processes are gracefully stopped with no zombies.

## Credential Safety in Logging

- Passwords and sensitive parameters are automatically redacted from logs.
- Publish URLs in log output appear as: `rtsp://username:***@host:port/path`.
- Special characters in credentials (`@`, `:`, `/`, `?`, `#`, `%`, `+`) are properly URL encoded.

## Running the Edge Gateway

### Direct Execution
```bash
python edge/ingest.py
```

### Systemd Deployment
Install the unit file `deploy/systemd/edge-ingest.service` on the edge gateway appliance:
```bash
sudo cp deploy/systemd/edge-ingest.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now edge-ingest
```
