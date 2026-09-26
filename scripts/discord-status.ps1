<#
.SYNOPSIS
    AURA Discord Bot - Status diagnostic script.
    Checks token presence, backend availability, Redis availability,
    and process status WITHOUT printing any secrets.
#>

param(
    [string]$BackendUrl = "http://localhost:8000",
    [string]$RedisUrl = "redis://localhost:6379/0"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  AURA Discord Bot - Diagnosis" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$issues = @()

# 1. Check .env for Discord credentials
$EnvFile = Resolve-Path "$PSScriptRoot\services\discord-bot\.env" -ErrorAction SilentlyContinue
$dotenv = $null
if ($EnvFile -and (Test-Path $EnvFile)) {
    $dotenv = @{}
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)=(.*)') {
            $dotenv[$matches[1].Trim()] = $matches[2].Trim()
        }
    }
}

$tokenPresent = $false
$clientIdPresent = $false
if ($dotenv) {
    $tokenPresent = $dotenv.ContainsKey("DISCORD_BOT_TOKEN") -and -not [string]::IsNullOrWhiteSpace($dotenv["DISCORD_BOT_TOKEN"])
    $clientIdPresent = $dotenv.ContainsKey("DISCORD_CLIENT_ID") -and -not [string]::IsNullOrWhiteSpace($dotenv["DISCORD_CLIENT_ID"])
}

Write-Host ""
Write-Host "[1/4] Configuración Discord" -ForegroundColor Yellow
Write-Host "  DISCORD_BOT_TOKEN: $(if($tokenPresent) {'configurado'} else {'AUSENTE'})"
Write-Host "  DISCORD_CLIENT_ID: $(if($clientIdPresent) {'configurado'} else {'AUSENTE'})"
if (-not $tokenPresent) { $issues += "DISCORD_BOT_TOKEN no configurado" }
if (-not $clientIdPresent) { $issues += "DISCORD_CLIENT_ID no configurado" }

# 2. Check backend
Write-Host ""
Write-Host "[2/4] Backend AURA" -ForegroundColor Yellow
try {
    $backendResp = Invoke-WebRequest -Uri "$BackendUrl/health" -TimeoutSeconds 5 -ErrorAction Stop
    $backendReachable = $backendResp.StatusCode -ge 200 -and $backendResp.StatusCode -lt 300
    Write-Host "  Backend: $(if($backendReachable) {'reachable (' + $BackendUrl + ')'} else {'NO disponible'})"
} catch {
    $backendReachable = $false
    Write-Host "  Backend: NO disponible ($BackendUrl)"
    $issues += "Backend no disponible en $BackendUrl"
}

# 3. Check Redis
Write-Host ""
Write-Host "[3/4] Redis" -ForegroundColor Yellow
try {
    $redisUri = [System.Uri]$RedisUrl
    $tcp = New-Object System.Net.Sockets.TcpClient
    $connect = $tcp.BeginConnect($redisUri.Host, $redisUri.Port, $null, $null)
    $wait = $connect.AsyncWaitHandle.WaitOne(3000, $false)
    if ($wait) {
        $redisReachable = $true
        $tcp.EndConnect($connect)
        $tcp.Close()
    } else {
        $redisReachable = $false
    }
    Write-Host "  Redis: $(if($redisReachable) {'reachable (' + $RedisUrl + ')'} else {'NO disponible'})"
} catch {
    $redisReachable = $false
    Write-Host "  Redis: NO disponible ($RedisUrl)"
    $issues += "Redis no disponible en $RedisUrl"
}

# 4. Check Discord bot process
Write-Host ""
Write-Host "[4/4] Proceso Discord Bot" -ForegroundColor Yellow
$process = Get-Process ruby -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*bot.rb*" }
$discordRunning = $process -ne $null -and $process.Count -gt 0
if ($discordRunning) {
    Write-Host "  Proceso: RUNNING (PID $($process[0].Id))"
} else {
    Write-Host "  Proceso: NOT RUNNING"
    $issues += "Proceso de bot de Discord no detectado"
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
if ($issues.Count -eq 0) {
    Write-Host "  Status: HEALTHY" -ForegroundColor Green
} else {
    Write-Host "  Status: DEGRADED" -ForegroundColor Red
    Write-Host "  Issues:" -ForegroundColor Yellow
    $issues | ForEach-Object { Write-Host "    - $_" -ForegroundColor Red }
}
Write-Host "==========================================" -ForegroundColor Cyan
