@echo off
:: AURA Complete Launcher
:: Verifies everything and launches the full desktop app

title AURA Desktop

echo.
echo ========================================
echo   AURA Autonomous AI Ecosystem
echo   Desktop App Launcher
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11+ required. Get it from https://python.org
    pause
    exit /b 1
)
python --version

:: Check Node.js (optional)
node --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Node.js not found - frontend web mode unavailable (desktop app still works)
) else (
    echo [OK] Node.js found
)

:: Check Ruby (optional)
ruby --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Ruby not found - Discord bot unavailable (desktop app still works)
) else (
    echo [OK] Ruby found
)

:: Check/install Python dependencies
echo.
echo Checking Python dependencies...

python -c "import cv2" >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] opencv-python...
    python -m pip install -q opencv-python
)

python -c "import mediapipe" >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] mediapipe...
    python -m pip install -q mediapipe
)

python -c "import speech_recognition" >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] SpeechRecognition...
    python -m pip install -q SpeechRecognition
)

python -c "import pyttsx3" >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] pyttsx3...
    python -m pip install -q pyttsx3
)

python -c "import numpy" >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] numpy...
    python -m pip install -q numpy
)

python -c "import pyaudio" >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] pyaudio...
    python -m pip install -q pyaudio
)

echo [OK] Python dependencies ready

:: Verify .env exists
if not exist ".env" (
    if exist ".env.example" (
        echo [SETUP] Creating .env from .env.example...
        copy .env.example .env >nul
    )
)

echo.
echo ========================================
echo   Launching AURA Desktop
echo ========================================
echo.

:: Launch
start "" /B pythonw.exe aura_app.py

timeout /t 2 /nobreak >nul
exit
