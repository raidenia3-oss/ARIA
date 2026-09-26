# AURA OS - Windows Native Start
$backendRoot = "C:\Users\User\Downloads\AURA"

Write-Host ""
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host "  AURA OS - Backend Starting (Minimal Mode)" -ForegroundColor Cyan
Write-Host "=============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[*] Activating venv..." -ForegroundColor Yellow
. "C:\Users\User\Downloads\AURA\aura-os\venv\Scripts\Activate.ps1"

Write-Host "[*] Starting AURA Backend..." -ForegroundColor Yellow
Write-Host "    Backend: http://localhost:8000" -ForegroundColor Cyan
Write-Host "    Health:  curl http://localhost:8000/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "Presiona Ctrl+C para detener." -ForegroundColor Gray
Write-Host ""

Set-Location $backendRoot
$env:PYTHONPATH = $backendRoot
python -m uvicorn backend.main_minimal:app --host 0.0.0.0 --port 8000 --reload
