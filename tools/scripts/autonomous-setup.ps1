# scripts/autonomous-setup.ps1

Write-Host "AURA Autonomous Setup Agent (Windows PowerShell)" -ForegroundColor Cyan
Write-Host ""

# Verificar Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python not found. Install Python 3.10+ first." -ForegroundColor Red
    exit 1
}

# Ejecutar config agent (como modulo para evitar ModuleNotFoundError)
Write-Host "Starting config agent..." -ForegroundColor Yellow
python -m ame_backend.src.automation.config_agent

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Setup successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Opening browser (backend health)..." -ForegroundColor Yellow
    Start-Process "http://localhost:8000/health"
} else {
    Write-Host ""
    Write-Host "Setup failed. Check errors above." -ForegroundColor Red
    exit 1
}
