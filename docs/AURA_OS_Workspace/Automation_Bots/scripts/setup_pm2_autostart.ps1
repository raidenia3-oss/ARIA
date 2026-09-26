# AURA PM2 Autostart Setup (Windows)
# Run as Administrator: powershell -ExecutionPolicy Bypass -File setup_pm2_autostart.ps1

$PM2_GLOBAL = npm list -g pm2 2>&1 | Select-String "pm2"

if (-not $PM2_GLOBAL) {
    Write-Host "Installing PM2 globally..." -ForegroundColor Yellow
    npm install -g pm2
}

$AuraPath = "C:\Users\User\Downloads\AURA"
Set-Location $AuraPath

Write-Host "Starting AURA with PM2..." -ForegroundColor Cyan
pm2 start ecosystem.config.js --name aura-ecosystem

Write-Host "Saving PM2 state..." -ForegroundColor Cyan
pm2 save

Write-Host "Setting up Windows Task Scheduler autostart..." -ForegroundColor Cyan
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c cd $AuraPath && pm2 start ecosystem.config.js 2>&1 >> pm2-startup.log"
$trigger = New-ScheduledTaskTrigger -AtStartup
$principal = New-ScheduledTaskPrincipal -UserID "$env:USERNAME" -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName "AURA-Startup" -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force

Write-Host "✅ AURA will start automatically on Windows startup" -ForegroundColor Green
Write-Host "Manage with: pm2 start/stop/restart/logs aura-servidor-ame" -ForegroundColor Cyan
Write-Host "View logs: pm2 logs aura-servidor-ame" -ForegroundColor Cyan
