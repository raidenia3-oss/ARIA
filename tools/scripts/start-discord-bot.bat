@echo off
echo ==========================================
echo  AURA Discord Bot - Secure Start
echo ==========================================

set "RUBY_DIR=C:\Ruby33-x64"
set "BOT_DIR=%~dp0..\services\discord-bot"

echo [1/5] Checking Ruby...
if not exist "%RUBY_DIR%\bin\ruby.exe" (
    echo ERROR: Ruby not found at %RUBY_DIR%
    echo Install Ruby 3.3+ from https://rubyinstaller.org/
    pause
    exit /b 1
)

echo [2/5] Checking .env...
if not exist "%BOT_DIR%\.env" (
    echo WARNING: .env not found. Running with environment variables only.
)

echo [3/5] Installing dependencies...
cd /d "%~dp0..\services\discord-bot"
"%RUBY_DIR%\bin\bundle" install 2>nul
if errorlevel 1 (
    echo WARNING: bundle install had issues. Attempting to continue...
)

echo [4/5] Verifying configuration...
set "CONFIG_OK=1"
findstr /R /C:"^DISCORD_BOT_TOKEN=." "%BOT_DIR%\.env" >nul 2>&1
if errorlevel 1 (
    echo   DISCORD_BOT_TOKEN: MISSING
    set "CONFIG_OK=0"
) else (
    echo   DISCORD_BOT_TOKEN: configured
)
findstr /R /C:"^DISCORD_CLIENT_ID=." "%BOT_DIR%\.env" >nul 2>&1
if errorlevel 1 (
    echo   DISCORD_CLIENT_ID: MISSING
    set "CONFIG_OK=0"
) else (
    echo   DISCORD_CLIENT_ID: configured
)

if "%CONFIG_OK%"=="0" (
    echo.
    echo ERROR: Missing required Discord credentials.
    echo Edit %BOT_DIR%\.env and add DISCORD_BOT_TOKEN and DISCORD_CLIENT_ID
    pause
    exit /b 1
)

echo [5/5] Starting bot with reconnection...
echo.
echo Press Ctrl+C to stop
echo Making sure backend is reachable at http://localhost:8000...
curl.exe -s -o nul http://localhost:8000/health 2>nul
if errorlevel 1 (
    echo WARNING: Backend not reachable. Bot may not function fully.
) else (
    echo Backend: OK
)
echo.

cd /d "%BOT_DIR%"
"%RUBY_DIR%\bin\ruby" "%~dp0start-discord-bot.rb" 10
