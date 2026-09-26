# run_wifi.ps1 — Arranca el backend AURA en la red Wi-Fi local (0.0.0.0:8000)
# Uso: .\run_wifi.ps1

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "  ___  __ _ | |_  / _|  AURA Backend — Modo Wi-Fi local" -ForegroundColor Cyan
Write-Host " / _ \/ _` | |  \| |_   (FastAPI + uvicorn)" -ForegroundColor Cyan
Write-Host ""

# Detectar IP local IPv4 (excluye loopback 127.x y APIPA 169.254.x)
$ip = (
  Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object {
    $_.InterfaceAlias -notmatch 'Loopback' -and
    $_.IPAddress -notmatch '^127\.' -and
    $_.IPAddress -notmatch '^169\.254\.'
  } |
  Select-Object -First 1
).IPAddress

if (-not $ip) {
  Write-Host "ADVERTENCIA: No se detecto una IP de red local. Usando 127.0.0.1 (solo este equipo)." -ForegroundColor Yellow
  $ip = "127.0.0.1"
}

Write-Host "IP local detectada: $ip" -ForegroundColor Green
Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host ">>> ¡SISTEMA OPERATIVO AURA LISTO!" -ForegroundColor Green
Write-Host ">>> Accede al Dashboard desde tu movil o PC en:" -ForegroundColor Green
Write-Host ">>> http://${ip}:8000/dashboard" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Presiona Ctrl+C para detener el servidor." -ForegroundColor DarkGray
Write-Host ""

# Asegurar que las dependencias esten disponibles (no falla si ya existen)
$deps = @("fastapi", "uvicorn", "pyjwt", "python-dotenv", "python-multipart")
foreach ($pkg in $deps) {
  python -c "import importlib,sys; importlib.import_module('$($pkg -replace 'python-','').replace('pyjwt','jwt').replace('python-multipart','multipart')')" 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando $pkg ..." -ForegroundColor Yellow
    pip install $pkg 2>&1 | Out-Null
  }
}

# Iniciar uvicorn en todas las interfaces (accesible desde el movil en la misma Wi-Fi)
uvicorn ame_backend.src.main:app --host 0.0.0.0 --port 8000
