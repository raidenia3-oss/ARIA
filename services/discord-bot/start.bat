@echo off
echo ==========================================
echo  AURA Discord Bot - Start Script
echo ==========================================
echo.

set "RUBY_DIR=C:\Ruby33-x64"
set "BOT_DIR=%~dp0"

echo [1/4] Checking Ruby...
if not exist "%RUBY_DIR%\bin\ruby.exe" (
    echo ERROR: Ruby not found at %RUBY_DIR%
    echo Install Ruby 3.3+ from https://rubyinstaller.org/
    pause
    exit /b 1
)
echo Ruby found: %RUBY_DIR%\bin\ruby.exe

echo.
echo [2/4] Checking bundler...
"%RUBY_DIR%\bin\gem" list bundler -i >nul 2>&1
if errorlevel 1 (
    echo Installing bundler...
    "%RUBY_DIR%\bin\gem" install bundler
)
echo Bundler OK

echo.
echo [3/4] Checking .env configuration...
if not exist "%BOT_DIR%.env" (
    echo WARNING: .env not found. Copy .env.example to .env and configure it.
    if exist "%BOT_DIR%.env.example" (
        echo Copying .env.example to .env...
        copy "%BOT_DIR%.env.example" "%BOT_DIR%.env" >nul
    )
)
findstr /R /C:"^DISCORD_BOT_TOKEN=." "%BOT_DIR%.env" >nul
if errorlevel 1 (
    echo ERROR: DISCORD_BOT_TOKEN is missing in %BOT_DIR%.env
    exit /b 1
)
findstr /R /C:"^DISCORD_CLIENT_ID=." "%BOT_DIR%.env" >nul
if errorlevel 1 (
    echo ERROR: DISCORD_CLIENT_ID is missing in %BOT_DIR%.env
    exit /b 1
)
echo Configuration checked

echo.
echo [4/4] Installing dependencies...
cd /d "%BOT_DIR%"
"%RUBY_DIR%\bin\bundle" install
if errorlevel 1 (
    echo ERROR: bundle install failed
    pause
    exit /b 1
)
echo Dependencies OK

echo.
echo ==========================================
echo  Starting AURA Discord Bot...
echo ==========================================
echo.
echo Make sure:
echo   - Backend is running at http://localhost:8000
echo   - .env has DISCORD_BOT_TOKEN and DISCORD_CLIENT_ID
echo   - Redis is available at redis://localhost:6379/0
echo.
echo Press Ctrl+C to stop
echo.

"%RUBY_DIR%\bin\bundle" exec ruby "%BOT_DIR%bot.rb"
pause
