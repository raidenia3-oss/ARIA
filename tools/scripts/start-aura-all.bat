@echo off
REM =============================================================================
REM  AURA all-in-one launcher (Windows dev) — Backend FastAPI + Discord bot
REM  -----------------------------------------------------------------------------
REM  Usage:
REM      scripts\start-aura-all.bat            # lanza backend y bot
REM      scripts\start-aura-all.bat -stop      # detiene procesos levantados
REM      scripts\start-aura-all.bat -status     # chequea /health
REM
REM  Logs:  data\aura-backend.log, data\discord-bot.log
REM  Lock:  data\aura-all.pid  (para -stop)
REM =============================================================================
setlocal enabledelayedexpansion

set "ROOT=%~dp0.."
pushd "%ROOT%" 2>nul || cd /d "%~dp0.."

if not exist data mkdir data

if /I "%~1"=="-stop" goto :stop
if /I "%~1"=="-status" goto :status

REM --- Backend FastAPI ---
echo [AURA] Starting backend (uvicorn backend.main:app @ 0.0.0.0:8000)...
start "AURA Backend" cmd /c ".venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 > data\aura-backend.log 2>&1"
REM --- Discord bot (usa start-discord-bot.rb: lock + dotenv + reintentos) ---
timeout /t 2 /nobreak >nul
echo [AURA] Starting Discord bot (ruby scripts\start-discord-bot.rb)...
start "AURA Discord Bot" cmd /c "ruby scripts\start-discord-bot.rb > data\discord-bot.log 2>&1"
echo %!ERRORLEVEL! > data\aura-all.pid.dummy

echo.
echo [AURA] Listo.
echo        Backend : http://localhost:8000  (^>^/health ^|^^ /docs)
echo        Bot logs : data\discord-bot.log
echo        BE logs  : data\aura-backend.log
echo        Stop with: scripts\start-aura-all.bat -stop
goto :eof

:stop
echo [AURA] Stopping AURA backend + Discord bot...
for /f "tokens=2 delims==." %%i in ('tasklist /fi "imagename eq python.exe" /fo csv 2^>nul ^| find "uvicorn"') do (
    echo [AURA] killing backend pid %%i
    taskkill /PID %%i /F 2>nul
)
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq ruby.exe" /fo csv 2^>nul ^| find "bot"') do (
    echo [AURA] killing ruby pid %%p
    taskkill /PID %%p /F 2>nul
)
if exist data\discord_bot.lock del /q data\discord_bot.lock
echo [AURA] Stopped.
goto :eof

:status
where curl >nul 2>nul && (
    curl -s -m 3 http://localhost:8000/health
    echo.
) || (
    powershell -NoProfile -c "try { (iwr -s -m 3 http://localhost:8000/health).Content } catch { 'no backend'"
)
goto :eof
