@echo off
echo ==========================================
echo  AURA Discord Bot - Status Check
echo ==========================================

set "RUBY_DIR=C:\Ruby33-x64"
set "BOT_DIR=%~dp0..\services\discord-bot"

echo [1/4] Checking Ruby...
if not exist "%RUBY_DIR%\bin\ruby.exe" (
    echo ERROR: Ruby not found at %RUBY_DIR%
    exit /b 1
)
echo Ruby found: %RUBY_DIR%\bin\ruby.exe

echo.
echo [2/4] Checking .env configuration...
if not exist "%BOT_DIR%\.env" (
    echo ERROR: .env not found in %BOT_DIR%
    exit /b 1
)

set "TOKEN_PRESENT=no"
findstr /R /C:"^DISCORD_BOT_TOKEN=." "%BOT_DIR%\.env" >nul
if not errorlevel 1 set "TOKEN_PRESENT=yes"

set "CLIENT_ID_PRESENT=no"
findstr /R /C:"^DISCORD_CLIENT_ID=." "%BOT_DIR%\.env" >nul
if not errorlevel 1 set "CLIENT_ID_PRESENT=yes"

echo DISCORD_BOT_TOKEN: %TOKEN_PRESENT%
echo DISCORD_CLIENT_ID: %CLIENT_ID_PRESENT%

echo.
echo [3/4] Checking backend connectivity...
curl.exe -s -o nul -w "%%HTTP_CODE%%" http://localhost:8000/health 2>nul | findstr /R /C:"^[23]" >nul
if not errorlevel 1 (
    echo Backend: reachable
) else (
    echo Backend: NOT reachable ^(http://localhost:8000/health^)
)

echo.
echo [4/4] Checking Discord bot process...
tasklist /FI "IMAGENAME eq ruby.exe" /FO CSV 2>nul | findstr /I "ruby.exe" >nul
if not errorlevel 1 (
    echo Discord bot process: RUNNING
) else (
    echo Discord bot process: NOT RUNNING
    echo Start with: services\discord-bot\start.bat
)

echo.
echo ==========================================
echo  Diagnosis complete
echo ==========================================
