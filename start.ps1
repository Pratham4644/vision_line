# Vision Line - Start all services
# Run from project root: .\start.ps1

$Root = $PSScriptRoot
Set-Location $Root

Write-Host "Starting Vision Line CCTV Platform..." -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
Write-Host "  1. MediaMTX  -> RTSP:8554, HLS:8888, WebRTC:8889, API:9997"
Write-Host "  2. FastAPI   -> http://127.0.0.1:8001"
Write-Host "  3. Caddy     -> https://localhost"
Write-Host ""
Write-Host "Open https://localhost in your browser (accept the local TLS cert)."
Write-Host "API docs: http://127.0.0.1:8001/docs"
Write-Host ""

# Start MediaMTX
Start-Process -FilePath "$Root\bin\mediamtx.exe" -ArgumentList "$Root\mediamtx.yml" -WorkingDirectory $Root -WindowStyle Normal

Start-Sleep -Seconds 2

# Start FastAPI
Start-Process -FilePath "$Root\.venv\Scripts\uvicorn.exe" -ArgumentList "main:app", "--host", "127.0.0.1", "--port", "8001", "--reload" -WorkingDirectory $Root -WindowStyle Normal

Start-Sleep -Seconds 2

# Start Caddy
Start-Process -FilePath "$Root\bin\caddy.exe" -ArgumentList "run", "--config", "$Root\Caddyfile" -WorkingDirectory $Root -WindowStyle Normal

Write-Host "All services started in separate windows." -ForegroundColor Green
