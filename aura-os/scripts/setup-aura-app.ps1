param()
$ErrorActionPreference = 'Stop'
$AURA_ROOT = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$APP_DIR = Join-Path $AURA_ROOT "AURA_APP"
$VENV = Join-Path $AURA_ROOT ".venv"

Write-Host "=== AURA App Setup ===" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $VENV "Scripts\python.exe"))) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
    python -m venv $VENV
}

Write-Host "Instalando dependencias..." -ForegroundColor Yellow
$REQ = Join-Path $APP_DIR "requirements.txt"
Push-Location $AURA_ROOT
& (Join-Path $VENV "Scripts\python.exe") -m pip install -r $REQ --quiet
Pop-Location

Write-Host "Verificando estructura..." -ForegroundColor Yellow
$dirs = @("frontend", "backend", "skills", "assets\voices", "logs", "memory")
foreach ($d in $dirs) {
    $path = Join-Path $APP_DIR $d
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
        Write-Host "  Creado: $d" -ForegroundColor Gray
    }
}

Write-Host "`n=== Setup completo ===" -ForegroundColor Green
Write-Host "Ejecuta start-aura-app.ps1 para iniciar" -ForegroundColor White
