# scripts/check-local.ps1

Write-Host "AURA Localhost Health Check" -ForegroundColor Cyan
Write-Host ""

# Detectar IP local (WiFi) - toma la primera IPv4 que no sea loopback
$localIP = ""
try {
    $adapters = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.InterfaceAlias -notmatch "Loopback" -and $_.IPAddress -ne "127.0.0.1" }
    if ($adapters) { $localIP = $adapters[0].IPAddress }
} catch {
    $ipLine = (ipconfig | Select-String "IPv4 Address" | Select-Object -First 1)
    if ($ipLine) { $localIP = ($ipLine.Line -replace '.*?:\s*' -replace '\s*$' -replace '[^0-9.]') }
}
Write-Host "Local Network IP: $localIP" -ForegroundColor Yellow
Write-Host ""

# Frontend
Write-Host -NoNewline "Frontend (localhost:3000): "
try {
    $null = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 3 -UseBasicParsing
    Write-Host "OK" -ForegroundColor Green
} catch {
    Write-Host "FAIL" -ForegroundColor Red
}

# Backend health (ame_backend exposes /health; telemetry app is mounted at /)
Write-Host -NoNewline "Backend (localhost:8000/health): "
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 3 -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "OK" -ForegroundColor Green
    } else {
        Write-Host "HTTP $($response.StatusCode)" -ForegroundColor Red
    }
} catch {
    Write-Host "FAIL" -ForegroundColor Red
}

# Archivos de configuracion locales
Write-Host -NoNewline "Config (.env files): "
if ((Test-Path "frontend/.env.local.dev") -and (Test-Path "backend/.env.local") -and (Test-Path "ame_backend/.env.local")) {
    Write-Host "OK" -ForegroundColor Green
} else {
    Write-Host "FAIL (faltan archivos)" -ForegroundColor Red
}

Write-Host ""
Write-Host "URLs:" -ForegroundColor Yellow
Write-Host "  Local:  http://localhost:3000" -ForegroundColor White
if ($localIP) { Write-Host "  WiFi:   http://$localIP`:3000" -ForegroundColor White }
Write-Host "  API:    http://localhost:8000/health" -ForegroundColor White
Write-Host ""
