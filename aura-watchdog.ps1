# AURA Watchdog - Autonomous Self-Healing System
# Runs every 5 minutes, monitors all services, repairs automatically.
# No human intervention required after initial setup.

$ErrorActionPreference = "SilentlyContinue"
$Root = "C:\Users\User\Downloads\AURA"
$ConfigDir = "$Root\.aura"
$ConfigFile = "$ConfigDir\config.json"
$LogFile = "$ConfigDir\watchdog.log"
$Fly = "C:\Users\User\.fly\bin\flyctl.exe"

function Write-Log {
    param($msg)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Add-Content -Path $LogFile -Value $line
    Write-Host $line -ForegroundColor Gray
}

function Get-Config {
    if (-not (Test-Path $ConfigFile)) { return $null }
    return Get-Content $ConfigFile -Raw | ConvertFrom-Json
}

function Set-Config {
    param($Config)
    $Config | ConvertTo-Json | Set-Content -Path $ConfigFile -Encoding UTF8
}

function Test-BackendHealth {
    param([string]$Url)
    try {
        $r = Invoke-WebRequest -Uri "$Url/health" -Method Get -TimeoutSec 5 -UseBasicParsing
        return $r.StatusCode -eq 200
    } catch { return $false }
}

function Test-DiscordBot {
    try {
        $status = & $Fly status --app aura-discord-bot 2>&1
        return $status -match "running"
    } catch { return $false }
}

function Repair-Backend {
    $config = Get-Config
    if (-not $config -or -not $config.backend_cloud_url) { return }
    
    $url = $config.backend_cloud_url
    if (-not (Test-BackendHealth -Url $url)) {
        Write-Log "Backend unhealthy, redeploying..."
        Set-Location "$Root\backend"
        & $Fly deploy --app aura-backend 2>&1 | Out-Null
        Write-Log "Backend redeploy attempted"
        Start-Sleep -Seconds 10
    }
}

function Repair-DiscordBot {
    $config = Get-Config
    if (-not $config -or -not $config.bot_deployed) { return }
    
    if (-not (Test-DiscordBot)) {
        Write-Log "Discord bot unhealthy, redeploying..."
        Set-Location "$Root\services\discord-bot"
        & $Fly deploy --app aura-discord-bot 2>&1 | Out-Null
        Write-Log "Discord bot redeploy attempted"
        Start-Sleep -Seconds 10
    }
}

function Repair-LocalBackend {
    $localBackend = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*backend.main*" }
    if (-not $localBackend) {
        Write-Log "Local backend not running, starting..."
        Start-Process -FilePath "python" -ArgumentList "-m", "backend.main", "--host", "0.0.0.0", "--port", "8000" -WorkingDirectory $Root -WindowStyle Hidden
        Write-Log "Local backend started"
    }
}

function Repair-Watchdog {
    $watchdog = Get-Process -Name "powershell" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*aura-watchdog*" }
    if (-not $watchdog) {
        Write-Log "Watchdog not running, restarting..."
        Start-Process -FilePath "powershell.exe" -ArgumentList "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Root\aura-watchdog.ps1`"" -WorkingDirectory $Root
        Write-Log "Watchdog restarted"
    }
}

# Main watchdog loop
Write-Log "Watchdog started"

while ($true) {
    $config = Get-Config
    
    if ($null -eq $config -or -not $config.setup_completed) {
        Write-Log "Setup not completed, waiting..."
        Start-Sleep -Seconds 60
        continue
    }
    
    # Repair cloud services
    if ($config.backend_deployed) {
        Repair-Backend
    }
    
    if ($config.bot_deployed) {
        Repair-DiscordBot
    }
    
    # Repair local backend if PC is on
    Repair-LocalBackend
    
    # Repair watchdog itself
    Repair-Watchdog
    
    Start-Sleep -Seconds 300  # Check every 5 minutes
}
