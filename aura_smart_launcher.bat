@echo off
:: AURA Smart Launcher
:: Checks dependencies and installs missing ones, then launches the app

title AURA Desktop

echo.
echo ========================================
echo   AURA Smart Launcher
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

echo [OK] Python found

:: Check and install dependencies
echo.
echo Checking dependencies...

set MISSING=0

python -c "import cv2" >nul 2>&1
if errorlevel 1 (
    echo [MISSING] opencv-python - installing...
    python -m pip install -q opencv-python
    set MISSING=1
) else (
    echo [OK] opencv-python
)

python -c "import mediapipe" >nul 2>&1
if errorlevel 1 (
    echo [MISSING] mediapipe - installing...
    python -m pip install -q mediapipe
    set MISSING=1
) else (
    echo [OK] mediapipe
)

python -c "import speech_recognition" >nul 2>&1
if errorlevel 1 (
    echo [MISSING] SpeechRecognition - installing...
    python -m pip install -q SpeechRecognition
    set MISSING=1
) else (
    echo [OK] SpeechRecognition
)

python -c "import pyttsx3" >nul 2>&1
if errorlevel 1 (
    echo [MISSING] pyttsx3 - installing...
    python -m pip install -q pyttsx3
    set MISSING=1
) else (
    echo [OK] pyttsx3
)

python -c "import numpy" >nul 2>&1
if errorlevel 1 (
    echo [MISSING] numpy - installing...
    python -m pip install -q numpy
    set MISSING=1
) else (
    echo [OK] numpy
)

python -c "import pyaudio" >nul 2>&1
if errorlevel 1 (
    echo [MISSING] pyaudio - installing...
    python -m pip install -q pyaudio
    set MISSING=1
) else (
    echo [OK] pyaudio
)

if %MISSING%==1 (
    echo.
    echo [INFO] Dependencies installed. Starting AURA...
) else (
    echo.
    echo [OK] All dependencies satisfied
)

echo.
echo ========================================
echo   Launching AURA Desktop
echo ========================================
echo.

:: Launch without console window
start "" /B pythonw.exe aura_app.py
