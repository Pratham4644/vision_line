# Operational Troubleshooting Guide

## 1. Stream Offline or Degraded
- **Symptoms**: Camera displays `OFFLINE` badge; WebRTC player shows reconnect spinner.
- **Diagnostic Steps**:
  1. Check System Health page (`/health`) or GET `/api/v1/health/streams`.
  2. Verify if MediaMTX is running:
     ```bash
     systemctl status mediamtx
     ```
  3. Inspect backend logs filtered by camera ID:
     Navigate to `/logs` in the dashboard, select Category: `STREAM` or `CAMERA`, and enter the camera ID.
  4. Test raw RTSP connectivity from the VM:
     ```bash
     ffprobe -rtsp_transport tcp -v error -show_entries stream=codec_name "rtsp://username:password@<camera_ip>:554/stream"
     ```

## 2. WebRTC Peer Connection Fails / ICE Disconnected
- **Symptoms**: WebRTC negotiation completes, but video never renders.
- **Root Causes**:
  - UDP port 8189 is blocked by Azure NSG or firewall.
  - MediaMTX `webrtcAdditionalHosts` is missing the Azure public IP (`20.194.48.89`).
- **Remedy**:
  - Ensure Azure Network Security Group allows inbound UDP on port 8189.
  - Verify that `streaming/mediamtx/mediamtx.yml` has `webrtcAdditionalHosts: [20.194.48.89]`.

## 3. High Latency or Packet Loss
- **Symptoms**: Video stutters or lags behind real-time by multiple seconds.
- **Remedy**:
  - Verify that the camera stream is H.264 so FFmpeg can run in passthrough mode (`-c:v copy`).
  - Ensure the RTSP transport is forced to TCP (`-rtsp_transport tcp`) to prevent UDP drop-bursts on Wi-Fi/cellular edge connections.
  - Disable any intermediate transcoding buffers.
