@echo off
title ARIA v6.0 - Full Autonomous Launcher
cd /d C:\Users\User\Downloads\AURA

echo ========================================
echo ARIA v6.0 - Starting Full Autonomous Mode
echo ========================================

REM Check/start Axum backend (port 8002)
echo [1/3] Checking Axum backend (port 8002)...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8002/health' -TimeoutSeconds 5; if ($r.StatusCode -eq 200) { Write-Output 'Axum running' } } catch { }" 2>nul
if errorlevel 1 (
    echo Starting Axum PoC...
    v6\axum-poc\target\debug\aria-axum-poc.exe
) else (
    echo Axum backend OK
)

timeout /t 2 /nobreak > nul

REM Start USB-ARIA agent in background
echo [2/3] Starting USB-ARIA agent...
start /min "ARIA-USB-Agent" cmd /c "C:\Users\User\Downloads\AURA\start_usb_agent.bat"

REM Start Autonomous Controller in background
echo [3/3] Starting Autonomous Controller...
start /min "ARIA-Autonomous" cmd /c "C:\Users\User\Downloads\AURA\start_autonomous.bat"

echo.
echo ========================================
echo All systems launched:
echo - Axum PoC: http://127.0.0.1:8002
echo - USB-ARIA Agent: polling daemon endpoints
echo - Autonomous Controller: self-improvement loop
echo ========================================
echo.

REM Keep window open
pause