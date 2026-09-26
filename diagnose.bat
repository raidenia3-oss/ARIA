@echo off
:: AURA Full System Diagnostic
:: Checks everything before launching

title AURA Diagnostic

echo.
echo ========================================
echo   AURA System Diagnostic
echo ========================================
echo.

set ERRORS=0

:: Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11+ NOT FOUND
    set ERRORS=1
) else (
    echo [OK] Python found
)

:: Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Node.js NOT FOUND (optional)
) else (
    echo [OK] Node.js found
)

:: Ruby
ruby --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Ruby NOT FOUND (optional)
) else (
    echo [OK] Ruby found
)

:: OpenCV
python -c "import cv2" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] opencv-python NOT FOUND
    set ERRORS=1
) else (
    echo [OK] opencv-python
)

:: MediaPipe
python -c "import mediapipe" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] mediapipe NOT FOUND
    set ERRORS=1
) else (
    echo [OK] mediapipe
)

:: SpeechRecognition
python -c "import speech_recognition" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] SpeechRecognition NOT FOUND
    set ERRORS=1
) else (
    echo [OK] SpeechRecognition
)

:: pyttsx3
python -c "import pyttsx3" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pyttsx3 NOT FOUND
    set ERRORS=1
) else (
    echo [OK] pyttsx3
)

:: NumPy
python -c "import numpy" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] numpy NOT FOUND
    set ERRORS=1
) else (
    echo [OK] numpy
)

:: PyAudio
python -c "import pyaudio" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pyaudio NOT FOUND
    set ERRORS=1
) else (
    echo [OK] pyaudio
)

:: .env
if not exist ".env" (
    echo [WARN] .env NOT FOUND
) else (
    echo [OK] .env exists
)

:: VS Code extensions
if not exist ".vscode\extensions.json" (
    echo [WARN] .vscode/extensions.json NOT FOUND
) else (
    echo [OK] .vscode configured
)

echo.
if %ERRORS%==1 (
    echo [RESULT] System has ERRORS - run install_dependencies.bat
) else (
    echo [RESULT] System OK - ready to launch
)
echo.
pause
