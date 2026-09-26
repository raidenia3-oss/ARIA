<#
.SYNOPSIS
    AURA all-in-one launcher (PowerShell) — Backend FastAPI + Discord bot with restart.
.DESCRIPTION
    Lanza backend y bot como jobs; reinicia on crash hasta -MaxRestarts.
.EXAMPLE
    .\scripts\start-aura-all.ps1           # lanza
    .\scripts\start-aura-all.ps1 -Stop      # detiene
    .\scripts\start-aura-all.ps1 -Status    # chequea /health
#>
param(
    [switch]$Stop,
    [switch]$Status,
    [int]$MaxRestarts = 10
)

$Root = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $Root
$data = Join-Path $Root 'data'
if (-not (Test-Path $data)) { New-Item -ItemType Directory -Path $data | Out-Null }

$backendLog  = Join-Path $data 'aura-backend.log'
$botLog      = Join-Path $data 'discord-bot.log'
$pidFile     = Join-Path $data 'aura-all.pid'

if ($Stop) {
    Get-ChildItem $pidFile,$botLock -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-Process -Name 'python','ruby' -ErrorAction SilentlyContinue |
        Where-Object { $_.Modules.FileName -match 'uvicorn|bot\.rb' } | Stop-Process -Force
    Write-Host '[AURA] Stopped.'
    return
}
if ($Status) {
    try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://localhost:8000/health').Content }
    catch { 'no backend' }
    return
}

# --- Backend ---
$be = Start-Process -FilePath "$Root\.venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn backend.main:app --host 0.0.0.0 --port 8000" `
    -RedirectStandardOutput $backendLog -RedirectStandardError $backendLog -PassThru -WindowStyle Hidden
"Backend PID $($be.Id)" | Out-File $pidFile

# --- Discord bot ---
Start-Sleep -Seconds 2
$bot = Start-Process -FilePath 'ruby' -ArgumentList 'scripts\start-discord-bot.rb' `
    -RedirectStandardOutput $botLog -RedirectStandardError $botLog -PassThru -WindowStyle Hidden

Write-Host "`n[AURA] Ready.  Backend: http://localhost:8000  |  Bot logs: $botLog"
Write-Host '[AURA] Stop with: .\scripts\start-aura-all.ps1 -Stop'
