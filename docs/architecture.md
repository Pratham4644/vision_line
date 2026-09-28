# Multi-Camera Streaming Platform Architecture

## 1. Overview
The Multi-Camera Streaming Platform is a high-performance, low-latency video surveillance and streaming system designed for multi-tenant and multi-site environments. It connects RTSP/IP cameras, CCTV systems, NVRs, and mobile edge cameras via FFmpeg and MediaMTX to WebRTC-enabled browser dashboards.

```
                    REMOTE SITE(S)

          [IP Camera / CCTV / NVR / Phone]
                         |
                        RTSP
                         |
                         v
              [Edge Stream Gateway]
                         |
                    FFmpeg Ingest
                         |
                   RTSP TCP Uplink
                         |
                         v
=====================================================
                    AZURE CLOUD
        VM: camera1.koreacentral.cloudapp.azure.com
                     (20.194.48.89)

                 [Nginx Reverse Proxy]
                  (Ports: 80 / 443 SSL)
                 /                   \
         WebRTC WHEP (8889)      HTTPS / API (8000)
               /                       \
              v                         v
     [MediaMTX v1.21.1]         [FastAPI Backend]
       RTSP Ingest: 8554               |
       WebRTC ICE: 8189 UDP            |-- Auth & RBAC
       WHEP API: 8889                  |-- Camera & Site CRUD
                                       |-- Stream Supervisor
                                       |-- Structured Audit Logging
                                       |-- System Health Monitoring
                                       |
                                       v
                             [MongoDB Database]
                              (Managed / Atlas)
=====================================================
                    CLIENT TIER

              [React + Vite Dashboard]
             - WHEP WebRTC Realtime Player
             - Multi-Site Management
             - Live Audit Logs & Health
```

## 2. Core Principles
1. **Zero AI / Drone contamination**: Drone hardware protocols (BLE, locks) and heavy AI/ML packages (YOLO, Torch) are excluded from the active production runtime.
2. **MongoDB as Single Source of Truth**: All configuration, metadata, site topology, camera registries, active stream states, and audit logs are persisted in MongoDB.
3. **Low Latency First**: Uses H.264 stream passthrough (`-c:v copy`) over TCP to MediaMTX and WebRTC WHEP for browser playback, minimizing buffering and preventing frame backlog.
4. **Resilient Stream Supervision**: The backend StreamService monitors FFmpeg processes, detects stream degradation or loss, applies exponential backoff auto-reconnect, and maintains live stream status in the database.
5. **Strict RBAC Security**: Granular role-based access control with four roles: `SUPER_ADMIN`, `ADMIN`, `OPERATOR`, `VIEWER`.
