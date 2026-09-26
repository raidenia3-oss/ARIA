@echo off
:: AURA Dependencies Auto-Installer
:: Installs all required packages for voice, gestures, vision, and OSINT modules

title AURA - Installing Dependencies

echo.
echo ========================================
echo   AURA Dependencies Installer
echo ========================================
echo.

echo [1/4] Installing core Python dependencies...
python -m pip install -q --upgrade pip setuptools wheel
python -m pip install -q -r requirements.txt
echo [OK] Core dependencies installed

echo.
echo [2/4] Installing computer vision dependencies (MediaPipe, OpenCV)...
python -m pip install -q opencv-python mediapipe numpy
echo [OK] Vision dependencies installed

echo.
echo [3/4] Installing voice dependencies (STT, TTS, Audio)...
python -m pip install -q SpeechRecognition pyttsx3 pyaudio
echo [OK] Voice dependencies installed

echo.
echo [4/4] Verifying installations...
python -c "import cv2; print('OpenCV:', cv2.__version__)" 2>&1
python -c "import mediapipe; print('MediaPipe:', mediapipe.__version__)" 2>&1
python -c "import speech_recognition; print('SpeechRecognition: OK')" 2>&1
python -c "import pyttsx3; print('pyttsx3: OK')" 2>&1
python -c "import numpy; print('NumPy:', numpy.__version__)" 2>&1
python -c "import pyaudio; print('PyAudio: OK')" 2>&1

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo You can now run AURA Desktop:
echo   - Double-click: aura_app.bat
echo   - Or run: python aura_app.py
echo.
pause
