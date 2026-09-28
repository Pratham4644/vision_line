# Multi-Camera Streaming Platform

A production-grade, low-latency multi-camera video streaming and site management platform built with FastAPI, React, TypeScript, MediaMTX, FFmpeg, and MongoDB.

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0%2B-3178C6)](https://typescriptlang.org)
[![MediaMTX](https://img.shields.io/badge/MediaMTX-v1.21.1-orange)](https://github.com/bluenviron/mediamtx)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-v3-38B2AC)](https://tailwindcss.com)

---

## 1. Key Features
- **Low-Latency Streaming**: WebRTC WHEP playback (~150-400ms end-to-end) powered by MediaMTX v1.21.1.
- **RTSP Ingestion Pipeline**: Low-delay, copy-mode FFmpeg ingestion with automated reconnect and stream supervisor.
- **Multi-Site Hierarchy**: Enterprise topology supporting `Organization -> Sites -> Cameras`.
- **Role-Based Access Control (RBAC)**: Fine-grained permissions across 4 roles: `SUPER_ADMIN`, `ORG_ADMIN`, `OPERATOR`, `VIEWER`.
- **MongoDB Persistence**: Modern PyMongo Async API integration with automated indexing and fail-closed security.
- **Structured Audit Logging**: Category-level logging with URL sanitization and credential masking.
- **System Health Monitoring**: Real-time status for backend, database, MediaMTX, FFmpeg, and individual stream workers.
- **No AI / Drone Contamination**: Excludes heavy ML packages (YOLO, PyTorch) and drone control logic from active runtime.

---

## 2. Architecture Overview
```
[Camera Source: RTSP/IP/NVR]
           |
          RTSP (TCP)
           v
[Edge Stream Gateway / FFmpeg Ingestion]
  -fflags nobuffer -flags low_delay -c:v copy
           |
          RTSP
           v
[MediaMTX Streaming Core (:8554, :8889, :8189 UDP)]
           |
         WebRTC (WHEP)
           v
[React Vite Dashboard / WHEP WebRTC Player]
```

---

## 3. Quick Start (Local Development)

### 3.1 Backend
```bash
# 1. Virtualenv & dependencies
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r backend/requirements.txt

# 2. Environment
cp .env.example .env

# 3. Seed initial Super Admin & Default Organization
python scripts/seed_admin.py

# 4. Launch backend
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

### 3.2 Frontend
```bash
cd frontend
npm install
npm run dev
```

### 3.3 Default Administrator Login
- **URL**: `http://localhost:5173` (or production portal)
- **Email**: `admin@platform.local`
- **Password**: `adminpassword123`

---

## 4. Production Deployment (Azure VM)
To deploy to the target Azure Ubuntu VM:
```bash
bash scripts/deploy_azure.sh
```
This script automates:
1. Python virtualenv and dependency synchronization
2. Frontend production SPA asset bundling (`npm run build`)
3. MediaMTX and Backend systemd service updates (`systemctl restart camera-platform-backend mediamtx`)
4. Nginx reverse proxy configuration reload with SSL and direct `/healthz` routing
5. Automated health check verification against the live server

---

## 5. Documentation
Comprehensive guides are available in the [`docs/`](docs/) directory:
- [Architecture & Design](docs/architecture.md)
- [Setup & Local Development](docs/setup.md)
- [Azure VM Deployment Guide](docs/deployment.md)
- [Streaming & Low-Latency Pipeline](docs/streaming.md)
- [MediaMTX Configuration & Operations](docs/mediamtx.md)
- [FFmpeg Ingestion Engine](docs/ffmpeg.md)
- [Database & MongoDB Schemas](docs/database.md)
- [Authentication & RBAC Matrix](docs/authentication.md)
- [Structured Logging](docs/logging.md)
- [Troubleshooting & Diagnostics](docs/troubleshooting.md)

---

## 6. Automated Test Suite
Run the comprehensive test suite with pytest:
```bash
pytest -v
```
**75 passed tests** (0 failures, 0 errors) validate:
- Authentication, session security & HttpOnly cookies
- Role-Based Access Control (RBAC) across 4 roles
- Strict multi-tenant isolation
- Camera credential encryption (Fernet AES/HMAC)
- Media plane, WHEP negotiation & edge ingestion supervision
- Audit logging & administrative operations
- Health & readiness probes (`/healthz`, `/api/v1/health`)

