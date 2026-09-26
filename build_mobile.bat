@echo off
chcp 65001 >nul
echo ==========================================
echo AURA Mobile Build — APK Builder
echo ==========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+
    pause
    exit /b 1
)

REM Install build dependencies
echo [1/4] Installing build dependencies...
pip install buildozer kivy plyer cryptography -q
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

REM Check Android SDK
echo [2/4] Checking Android SDK...
if not exist "%ANDROID_HOME%" (
    echo [WARN] ANDROID_HOME not set. Please install Android Studio and set ANDROID_HOME.
    echo       For now, generating desktop build only.
    goto :desktop_build
)

REM Build APK
echo [3/4] Building APK...
buildozer android debug
if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo [4/4] APK built successfully!
echo Location: bin\AURA-0.1-debug.apk
pause
exit /b 0

:desktop_build
echo [3/4] Building desktop executable...
pip install pyinstaller -q
pyinstaller --onefile --windowed --name AURA aura_app.py
echo [4/4] Desktop build complete!
echo Location: dist\AURA.exe
pause
