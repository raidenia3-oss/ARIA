# AURA - Deploy Automatico en Fly.io
# Ejecuta este script en PowerShell para deployear todo automaticamente

param(
    [switch]$SkipBot,
    [switch]$SkipBackend
)

$ErrorActionPreference = "Stop"
$Fly = "C:\Users\User\.fly\bin\flyctl.exe"
$Root = "C:\Users\User\Downloads\AURA"

function Test-Command($cmd) {
    try { & $cmd --version 2>&1 | Out-Null; return $true } catch { return $false }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  AURA Auto Deploy - Fly.io" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check flyctl
if (-not (Test-Command $Fly)) {
    Write-Host "ERROR: flyctl no encontrado en $Fly" -ForegroundColor Red
    Write-Host "Instalalo con: powershell -Command \"iwr https://fly.io/install.ps1 -UseBasicParsing | iex\"" -ForegroundColor Yellow
    exit 1
}

# Check login
$loginCheck = & $Fly auth whoami 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Necesitas login en Fly.io. Abriendo navegador..." -ForegroundColor Yellow
    & $Fly auth login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Login fallido" -ForegroundColor Red
        exit 1
    }
}

Write-Host "[OK] Fly.io login verificado" -ForegroundColor Green

# Deploy Backend
if (-not $SkipBackend) {
    Write-Host ""
    Write-Host "[1/2] Deploying backend..." -ForegroundColor Cyan
    
    Set-Location "$Root\backend"
    
    # Create app if not exists
    try {
        & $Fly apps list 2>&1 | Out-Null
    } catch {
        Write-Host "  Creating app aura-backend..." -ForegroundColor Yellow
        & $Fly apps create aura-backend 2>&1 | Out-Null
    }
    
    # Create volume if not exists
    try {
        & $Fly volumes list -a aura-backend 2>&1 | Out-Null
    } catch {
        Write-Host "  Creating volume aura_models (2GB)..." -ForegroundColor Yellow
        & $Fly volumes create aura_models --size 2 --region iad 2>&1 | Out-Null
    }
    
    # Set secrets
    Write-Host "  Setting secrets..." -ForegroundColor Yellow
    $env:AURA_API_KEY = if ($env:AURA_API_KEY) { $env:AURA_API_KEY } else { "dev-key-$(Get-Random)" }
    & $Fly secrets set AURA_API_KEY=$env:AURA_API_KEY --app aura-backend 2>&1 | Out-Null
    & $Fly secrets set AURA_LOCAL_MODEL_PATH="/app/models/qwen-0.5b" --app aura-backend 2>&1 | Out-Null
    & $Fly secrets set AURA_CORS_ORIGINS="*" --app aura-backend 2>&1 | Out-Null
    
    if ($env:GEMINI_API_KEY) {
        & $Fly secrets set GEMINI_API_KEY=$env:GEMINI_API_KEY --app aura-backend 2>&1 | Out-Null
    }
    if ($env:GROQ_API_KEY) {
        & $Fly secrets set GROQ_API_KEY=$env:GROQ_API_KEY --app aura-backend 2>&1 | Out-Null
    }
    if ($env:OPENROUTER_API_KEY) {
        & $Fly secrets set OPENROUTER_API_KEY=$env:OPENROUTER_API_KEY --app aura-backend 2>&1 | Out-Null
    }
    
    # Deploy
    Write-Host "  Deploying backend (esto puede tardar 2-3 minutos)..." -ForegroundColor Yellow
    & $Fly deploy --app aura-backend 2>&1 | Out-Null
    
    Write-Host "[OK] Backend deployed!" -ForegroundColor Green
    
    # Get URL
    $backendUrl = (& $Fly info --app aura-backend --json 2>&1 | ConvertFrom-Json).Hostname
    Write-Host "  URL: https://$backendUrl" -ForegroundColor Green
    
    # Save URL for bot
    $env:AURA_BACKEND_URL = "https://$backendUrl"
} else {
    Write-Host "[SKIP] Backend deploy" -ForegroundColor Yellow
}

# Deploy Discord Bot
if (-not $SkipBot) {
    Write-Host ""
    Write-Host "[2/2] Deploying Discord bot..." -ForegroundColor Cyan
    
    Set-Location "$Root\services\discord-bot"
    
    # Check required env vars
    if (-not $env:DISCORD_BOT_TOKEN -or -not $env:DISCORD_CLIENT_ID -or -not $env:DISCORD_GUILD_ID) {
        Write-Host "  WARNING: Discord credentials missing. Set DISCORD_BOT_TOKEN, DISCORD_CLIENT_ID, DISCORD_GUILD_ID" -ForegroundColor Yellow
        Write-Host "  Skipping bot deploy. Run later with:" -ForegroundColor Yellow
        Write-Host "    `$env:DISCORD_BOT_TOKEN='token'; `$env:DISCORD_CLIENT_ID='id'; `$env:DISCORD_GUILD_ID='guild'; .\deploy.ps1 -SkipBackend" -ForegroundColor Yellow
    } else {
        try {
            & $Fly apps list 2>&1 | Out-Null
        } catch {
            & $Fly apps create aura-discord-bot 2>&1 | Out-Null
        }
        
        Write-Host "  Setting bot secrets..." -ForegroundColor Yellow
        & $Fly secrets set DISCORD_BOT_TOKEN=$env:DISCORD_BOT_TOKEN --app aura-discord-bot 2>&1 | Out-Null
        & $Fly secrets set DISCORD_CLIENT_ID=$env:DISCORD_CLIENT_ID --app aura-discord-bot 2>&1 | Out-Null
        & $Fly secrets set DISCORD_GUILD_ID=$env:DISCORD_GUILD_ID --app aura-discord-bot 2>&1 | Out-Null
        
        if ($env:AURA_BACKEND_URL) {
            & $Fly secrets set AURA_BACKEND_URL=$env:AURA_BACKEND_URL --app aura-discord-bot 2>&1 | Out-Null
        }
        
        Write-Host "  Deploying bot..." -ForegroundColor Yellow
        & $Fly deploy --app aura-discord-bot 2>&1 | Out-Null
        
        Write-Host "[OK] Discord bot deployed!" -ForegroundColor Green
    }
} else {
    Write-Host "[SKIP] Discord bot deploy" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  DEPLOY COMPLETE!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Test backend: curl https://<backend-url>/health" -ForegroundColor White
Write-Host "  2. Test chat: curl -X POST https://<backend-url>/api/chat -H 'Content-Type: application/json' -d '{\"prompt\":\"hola\"}'" -ForegroundColor White
Write-Host "  3. Build Android: open dist/Build_Android.bat" -ForegroundColor White
Write-Host ""
