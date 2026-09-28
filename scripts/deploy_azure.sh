#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Remote Camera Streaming Platform - Azure VM Production Deployment Script
# Target: Ubuntu 22.04 LTS on Azure VM (camera1.koreacentral.cloudapp.azure.com)
# ==============================================================================

DEPLOY_DIR="/opt/camera-platform"
VENV_DIR="${DEPLOY_DIR}/.venv"
FRONTEND_DIR="${DEPLOY_DIR}/frontend"

echo "=== [1/7] Deploying Remote Camera Streaming Platform ==="
cd "${DEPLOY_DIR}"

# 1. Update Python dependencies
echo "=== [2/7] Syncing Python dependencies ==="
if [ ! -d "${VENV_DIR}" ]; then
    echo "Creating virtual environment at ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
fi
"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel
"${VENV_DIR}/bin/pip" install -r requirements.txt

# 2. Build Frontend Production Assets
echo "=== [3/7] Building Frontend SPA Assets ==="
cd "${FRONTEND_DIR}"
npm install --no-audit --no-fund
npm run build
cd "${DEPLOY_DIR}"

# 3. Configure Systemd Services
echo "=== [4/7] Installing Systemd unit files ==="
sudo cp deploy/systemd/camera-platform-backend.service /etc/systemd/system/
sudo cp deploy/systemd/mediamtx.service /etc/systemd/system/
sudo systemctl daemon-reload

# 4. Configure Nginx
echo "=== [5/7] Updating Nginx configuration ==="
if [ -f "deploy/nginx/camera1.koreacentral.cloudapp.azure.com.conf" ]; then
    sudo cp deploy/nginx/camera1.koreacentral.cloudapp.azure.com.conf /etc/nginx/sites-available/
    sudo ln -sf /etc/nginx/sites-available/camera1.koreacentral.cloudapp.azure.com.conf /etc/nginx/sites-enabled/
    sudo nginx -t
    sudo systemctl reload nginx
fi

# 5. Restart Backend and MediaMTX services
echo "=== [6/7] Restarting backend services ==="
sudo systemctl enable camera-platform-backend mediamtx
sudo systemctl restart mediamtx
sleep 2
sudo systemctl restart camera-platform-backend
sleep 3

# 6. Verify Health
echo "=== [7/7] Verifying health endpoints ==="
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/healthz || echo "000")
if [ "$HEALTH_STATUS" -eq 200 ]; then
    echo "✓ Platform Backend is healthy (HTTP 200 on /healthz)"
else
    echo "⚠ Healthcheck returned HTTP $HEALTH_STATUS. Checking systemctl status..."
    sudo systemctl status camera-platform-backend --no-pager
    exit 1
fi

echo "=============================================================================="
echo "✓ Production deployment completed successfully!"
echo "Web portal:  https://camera1.koreacentral.cloudapp.azure.com"
echo "API docs:    https://camera1.koreacentral.cloudapp.azure.com/docs"
echo "=============================================================================="
