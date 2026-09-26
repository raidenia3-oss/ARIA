@echo off
:: AURA Launcher for Windows
:: Double-click this file to start AURA in development mode

title AURA - Autonomous AI Ecosystem

echo.
echo ========================================
echo   AURA Development Launcher
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

:: Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Node.js not found. Frontend will be skipped.
)

:: Check Ruby
ruby --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Ruby not found. Discord bot will be skipped.
)

echo [INFO] Starting AURA in development mode...
echo.

:: Start AURA
python aura.py

pause
