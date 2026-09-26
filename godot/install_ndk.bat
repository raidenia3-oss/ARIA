@echo off
setlocal
chcp 65001 >nul
title AURA - Install Android NDK

set "SDK=%LOCALAPPDATA%\Android\Sdk"
set "NDK_DIR=%SDK%\ndk\25.1.8937393"
set "NDK_ZIP=%TEMP%\android-ndk-r25b-windows.zip"
set "NDK_URL=https://github.com/android/ndk/releases/download/r25b/android-ndk-r25b-windows.zip"

echo ==========================================
echo   AURA - Install Android NDK r25
echo ==========================================
echo.

if exist "%NDK_DIR%\source.properties" (
    echo [OK] NDK ya instalado en: %NDK_DIR%
    pause
    exit /b 0
)

echo [INFO] NDK no encontrado. Se descargara e instalara automaticamente.
echo URL: %NDK_URL%
echo Destino: %NDK_DIR%
echo.
echo Esto puede tardar varios minutos...
echo.

if not exist "%SDK%\ndk" mkdir "%SDK%\ndk"

echo [1/2] Descargando NDK...
powershell -Command "Invoke-WebRequest -Uri '%NDK_URL%' -OutFile '%NDK_ZIP%' -UseBasicParsing"
if errorlevel 1 (
    echo [ERROR] Fallo la descarga del NDK.
    echo Descargalo manualmente desde:
    echo https://developer.android.com/studio#downloads
    pause
    exit /b 1
)

echo [2/2] Extrayendo NDK...
powershell -Command "Expand-Archive -Path '%NDK_ZIP%' -DestinationPath '%SDK%\ndk' -Force"
if errorlevel 1 (
    echo [ERROR] Fallo la extraccion.
    pause
    exit /b 1
)

ren "%SDK%\ndk\android-ndk-r25b" "25.1.8937393" >nul 2>&1

if exist "%NDK_DIR%\source.properties" (
    echo [OK] NDK instalado correctamente en: %NDK_DIR%
) else (
    echo [ERROR] NDK no quedo correctamente instalado.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Instalacion completada
echo ==========================================
pause
endlocal
