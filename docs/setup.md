# Setup and Local Development Guide

## 1. Prerequisites
- Python 3.11+ (Python 3.12 or 3.13 recommended)
- Node.js 18+ and npm
- FFmpeg installed and available on PATH
- MediaMTX v1.21.1 binary
- MongoDB (local instance or MongoDB Atlas free tier URI)

## 2. Quick Local Start

### 2.1 Backend Setup
```bash
# 1. Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Create .env file from template
cp .env.example .env
# Edit .env with your MongoDB URI or use mock/local MongoDB

# 4. Seed development database
python scripts/seed_dev.py

# 5. Run FastAPI Backend Server
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2.2 Frontend Setup
```bash
cd frontend
npm install
npm run dev
# The frontend development server runs at http://localhost:5173
```

### 2.3 MediaMTX Setup
Download MediaMTX v1.21.1:
```bash
# Run MediaMTX with the canonical configuration:
mediamtx streaming/mediamtx/mediamtx.yml
```

### 2.4 Default Development Credentials
- **Email**: `admin@camera-platform.local`
- **Password**: `admin12345`
- **Role**: `SUPER_ADMIN`
- **Organization**: `Alpha Security Operations` (`org-default`)
