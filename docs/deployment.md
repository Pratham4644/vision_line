# Azure VM Deployment Guide

## 1. Target Infrastructure Specs
- **VM Name**: `camerastream1`
- **Resource Group**: `camera_stream`
- **Region**: Korea Central
- **VM Size**: `Standard_B2ats_v2` (2 vCPU, 1 GiB RAM)
- **Public IP**: `20.194.48.89`
- **Hostname**: `camera1.koreacentral.cloudapp.azure.com`
- **OS**: Ubuntu 24.04 LTS x64
- **SSH User**: `azureuser`

## 2. Resource Governance on 1 GiB RAM
Because the VM has only 1 GiB RAM, memory discipline is paramount:
1. **Never install local MongoDB on the VM**: Use MongoDB Atlas (M0 Free Tier).
2. **Never install PyTorch / YOLO**: ML frameworks consume 1.5–3 GB RAM immediately causing kernel OOM killer panics.
3. **Use systemd memory quotas**:
   - `mediamtx.service`: `MemoryMax=350M`
   - `camera-platform-backend.service`: `MemoryMax=500M`
4. **Compile frontend assets locally or via CI**: Serve static files directly via Nginx.

## 3. Azure Network Security Group (NSG) Rules
| Port | Protocol | Purpose | Access |
|---|---|---|---|
| 22 | TCP | SSH Administration | Admin IP |
| 80 | TCP | HTTP (Redirects to 443) | Public |
| 443 | TCP | HTTPS Web & API | Public |
| 8554 | TCP | MediaMTX RTSP Ingest | Public / Edge Gateways |
| 8889 | TCP | MediaMTX WebRTC HTTP (WHEP) | Public (via Nginx or Direct) |
| 8189 | UDP | MediaMTX WebRTC ICE Media | Public |
| 8000 | TCP | Backend FastAPI | Internal Only (Proxy via Nginx) |
| 27017 | TCP | MongoDB | NEVER exposed on VM |

## 4. Deployment Steps

### Step 1: Backup Existing Configurations
```bash
sudo cp /etc/nginx/sites-available/default /etc/nginx/sites-available/default.backup-$(date +%s) || true
sudo cp /opt/mediamtx/mediamtx.yml /opt/mediamtx/mediamtx.yml.backup-$(date +%s) || true
```

### Step 2: MediaMTX Deployment
1. Copy `streaming/mediamtx/mediamtx.yml` to `/opt/camera-platform/mediamtx/mediamtx.yml`.
2. Install `deploy/systemd/mediamtx.service` into `/etc/systemd/system/`.
3. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable mediamtx
   sudo systemctl restart mediamtx
   sudo systemctl status mediamtx
   ```

### Step 3: Backend Deployment
1. Clone / rsync repository to `/opt/camera-platform`.
2. Create virtual environment and install dependencies:
   ```bash
   python3 -m venv /opt/camera-platform/.venv
   /opt/camera-platform/.venv/bin/pip install --upgrade pip
   /opt/camera-platform/.venv/bin/pip install -r /opt/camera-platform/backend/requirements.txt
   ```
3. Set `/opt/camera-platform/.env` with your MongoDB Atlas URI and JWT Secret:
   ```bash
   sudo chmod 600 /opt/camera-platform/.env
   sudo chown azureuser:azureuser /opt/camera-platform/.env
   ```
4. Copy `deploy/systemd/camera-platform-backend.service` to `/etc/systemd/system/`.
5. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable camera-platform-backend
   sudo systemctl restart camera-platform-backend
   sudo systemctl status camera-platform-backend
   ```

### Step 4: Nginx & SSL Verification
1. Copy `deploy/nginx/camera1.koreacentral.cloudapp.azure.com.conf` to `/etc/nginx/sites-available/`.
2. Enable site:
   ```bash
   sudo ln -sf /etc/nginx/sites-available/camera1.koreacentral.cloudapp.azure.com.conf /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```
3. Verify SSL certificate with Certbot:
   ```bash
   sudo certbot certificates
   ```
