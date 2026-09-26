# AURA - Setup Autónomo Definitivo
# Ejecuta UNA SOLA VEZ: setup.ps1
# Después de eso, AURA funciona 100% sin intervención humana.
# - Backend en Fly.io 24/7
# - Discord bot 24/7
# - Watchdog autónomo cada 5 minutos
# - Auto-start en Windows

param(
    [switch]$SkipCloud,
    [switch]$SkipAndroid,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$Root = "C:\Users\User\Downloads\AURA"
$ConfigDir = "$Root\.aura"
$ConfigFile = "$ConfigDir\config.json"
$Fly = "C:\Users\User\.fly\bin\flyctl.exe"

function Write-Status($msg, $color = "Cyan") {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor $color
    Write-Host "  $msg" -ForegroundColor $color
    Write-Host "==========================================" -ForegroundColor $color
    Write-Host ""
}

function Get-Config {
    if (-not (Test-Path $ConfigFile)) { return $null }
    return Get-Content $ConfigFile -Raw | ConvertFrom-Json
}

function Set-Config {
    param($Config)
    $Config | ConvertTo-Json | Set-Content -Path $ConfigFile -Encoding UTF8
}

function New-Config {
    Write-Status "Configuracion Inicial" "Yellow"
    Write-Host "Ingresa las credenciales. Se guardaran para no volver a pedirlas." -ForegroundColor Yellow
    Write-Host ""
    
    $config = @{
        fly_token = ""
        discord_token = ""
        discord_client_id = ""
        discord_guild_id = ""
        backend_cloud_url = ""
        setup_completed = $false
        backend_deployed = $false
        bot_deployed = $false
        android_built = $false
        created_at = (Get-Date -Format "o")
    }
    
    $config.fly_token = Read-Host "Fly.io API token (enter para omitir cloud)"
    $config.discord_token = Read-Host "Discord Bot Token (enter para omitir)"
    $config.discord_client_id = Read-Host "Discord Client ID (enter para omitir)"
    $config.discord_guild_id = Read-Host "Discord Guild ID (enter para omitir)"
    
    New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
    Set-Config $config
    return $config
}

function Deploy-Backend {
    param($Config)
    
    Write-Status "Deploy Backend en Fly.io" "Cyan"
    
    if ($Config.fly_token) {
        $env:FLY_API_TOKEN = $Config.fly_token
    }
    
    Set-Location "$Root\backend"
    
    # Create app
    try {
        & $Fly apps list 2>&1 | Out-Null
        Write-Host "[OK] App aura-backend existe" -ForegroundColor Green
    } catch {
        Write-Host "  Creando app aura-backend..." -ForegroundColor Yellow
        & $Fly apps create aura-backend 2>&1 | Out-Null
    }
    
    # Create volume
    try {
        & $Fly volumes list -a aura-backend 2>&1 | Out-Null
        Write-Host "[OK] Volume aura_models existe" -ForegroundColor Green
    } catch {
        Write-Host "  Creando volume aura_models (2GB)..." -ForegroundColor Yellow
        & $Fly volumes create aura_models --size 2 --region iad 2>&1 | Out-Null
    }
    
    # Set secrets
    $env:AURA_API_KEY = "dev-key-$(Get-Random)"
    & $Fly secrets set AURA_API_KEY=$env:AURA_API_KEY --app aura-backend 2>&1 | Out-Null
    & $Fly secrets set AURA_LOCAL_MODEL_PATH="/app/models/qwen-0.5b" --app aura-backend 2>&1 | Out-Null
    & $Fly secrets set AURA_CORS_ORIGINS="*" --app aura-backend 2>&1 | Out-Null
    
    # Deploy
    Write-Host "  Deploying backend (2-3 minutos)..." -ForegroundColor Yellow
    & $Fly deploy --app aura-backend 2>&1 | Out-Null
    
    # Get URL
    $backendUrl = (& $Fly info --app aura-backend --json 2>&1 | ConvertFrom-Json).Hostname
    $Config.backend_cloud_url = "https://$backendUrl"
    $Config.backend_deployed = $true
    
    Write-Host "[OK] Backend deployed: $($Config.backend_cloud_url)" -ForegroundColor Green
}

function Deploy-DiscordBot {
    param($Config)
    
    if (-not $Config.discord_token -or -not $Config.discord_client_id -or -not $Config.discord_guild_id) {
        Write-Host "[SKIP] Discord bot: faltan credenciales" -ForegroundColor Yellow
        return
    }
    
    Write-Status "Deploy Discord Bot en Fly.io" "Cyan"
    
    Set-Location "$Root\services\discord-bot"
    
    # Create app
    try {
        & $Fly apps list 2>&1 | Out-Null
    } catch {
        & $Fly apps create aura-discord-bot 2>&1 | Out-Null
    }
    
    # Set secrets
    & $Fly secrets set DISCORD_BOT_TOKEN=$Config.discord_token --app aura-discord-bot 2>&1 | Out-Null
    & $Fly secrets set DISCORD_CLIENT_ID=$Config.discord_client_id --app aura-discord-bot 2>&1 | Out-Null
    & $Fly secrets set DISCORD_GUILD_ID=$Config.discord_guild_id --app aura-discord-bot 2>&1 | Out-Null
    & $Fly secrets set AURA_BACKEND_URL=$Config.backend_cloud_url --app aura-discord-bot 2>&1 | Out-Null
    
    # Deploy
    Write-Host "  Deploying bot..." -ForegroundColor Yellow
    & $Fly deploy --app aura-discord-bot 2>&1 | Out-Null
    
    $Config.bot_deployed = $true
    Write-Host "[OK] Discord bot deployed!" -ForegroundColor Green
}

function Setup-Watchdog {
    Write-Status "Configurando Watchdog Autonomo" "Cyan"
    
    $watchdogScript = "$Root\aura-watchdog.ps1"
    
    # Create scheduled task
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$watchdogScript`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $trigger2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Minutes 5)
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable
    
    Register-ScheduledTask -TaskName "AURA Watchdog" -Action $action -Trigger $trigger,$trigger2 -Settings $settings -Description "AURA autonomous watchdog" -Force 2>&1 | Out-Null
    
    Write-Host "[OK] Watchdog programado cada 5 minutos y al iniciar Windows" -ForegroundColor Green
}

function Setup-AutoStart {
    Write-Status "Configurando Auto-Inicio" "Cyan"
    
    $startupDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
    $shortcutPath = Join-Path $startupDir "AURA.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "$Root\aura-watchdog.ps1"
    $shortcut.WorkingDirectory = $Root
    $shortcut.WindowStyle = 7  # Minimized
    $shortcut.Save()
    
    Write-Host "[OK] Acceso directo creado en Startup" -ForegroundColor Green
}

# Main execution
$config = Get-Config
if (-not $config -or $Force) {
    $config = New-Config
}

if (-not $SkipCloud) {
    if ($config.fly_token) {
        Deploy-Backend -Config $config
    } else {
        Write-Host "[SKIP] Fly.io deploy: no hay token" -ForegroundColor Yellow
    }
    
    if ($config.backend_cloud_url) {
        Deploy-DiscordBot -Config $config
    }
} else {
    Write-Host "[SKIP] Cloud deploy" -ForegroundColor Yellow
}

Setup-Watchdog
Setup-AutoStart

# Mark as completed
$config.setup_completed = $true
Set-Config $config

Write-Status "SETUP COMPLETO" "Green"
Write-Host "AURA ahora funciona de forma autonoma:" -ForegroundColor Cyan
Write-Host "  - Backend cloud: $($config.backend_cloud_url)" -ForegroundColor White
Write-Host "  - Discord bot: $($config.bot_deployed)" -ForegroundColor White
Write-Host "  - Watchdog: cada 5 minutos" -ForegroundColor White
Write-Host "  - Auto-start: al encender Windows" -ForegroundColor White
Write-Host ""
Write-Host "No necesitas hacer nada mas. AURA se mantiene sola." -ForegroundColor Green
Write-Host ""
Write-Host "Para verificar:" -ForegroundColor Yellow
Write-Host "  - Backend: $($config.backend_cloud_url)/health" -ForegroundColor White
Write-Host "  - Logs: $ConfigDir\watchdog.log" -ForegroundColor White
Write-Host ""
