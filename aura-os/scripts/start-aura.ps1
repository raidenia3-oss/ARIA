# AURA OS - Quick Start (WSL2)
# Doble clic para iniciar AURA backend
param()
$ErrorActionPreference = 'SilentlyContinue'

Write-Host ''
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host '  AURA OS - Iniciando...' -ForegroundColor Cyan
Write-Host '=============================================================' -ForegroundColor Cyan
Write-Host ''

# Verificar que WSL2 esté corriendo
$wslStatus = wsl --status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host '[ERR] WSL2 no esta instalado o no esta funcionando.' -ForegroundColor Red
    Write-Host '      Ejecuta install-wsl2.ps1 primero.' -ForegroundColor Yellow
    pause
    exit 1
}

# Iniciar AURA en WSL2
Write-Host 'Iniciando AURA Backend en WSL2...' -ForegroundColor Yellow
Write-Host 'Backend: http://localhost:8000' -ForegroundColor Cyan
Write-Host 'Health:  curl http://localhost:8000/health' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Presiona Ctrl+C para detener.' -ForegroundColor Gray
Write-Host ''

wsl -d AURA-OS -u root /usr/local/bin/start-aura.sh
