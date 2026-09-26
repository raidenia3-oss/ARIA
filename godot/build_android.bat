@echo off
setlocal
chcp 65001 >nul
title AURA - Build Android APK

set "AURA_ROOT=%~dp0..\"
set "GODOT=C:\Users\User\OneDrive\Escritorio\Godot_v4.6-stable_win64.exe"
set "EXPORT_PRESETS=%AURA_ROOT%godot\export_presets.cfg"
set "PROJECT=%AURA_ROOT%godot\project.godot"
set "DIST_DIR=%AURA_ROOT%dist"
set "APK_NAME=AURA_Android.apk"
set "JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot"
set "PATH=%JAVA_HOME%\bin;%PATH%"

echo ==========================================
echo   AURA - Android Build
echo ==========================================
echo.

if not exist "%GODOT%" (
    echo [ERROR] Godot no encontrado en: %GODOT%
    echo Ajusta la variable GODOT en este script.
    pause
    exit /b 1
)

if not exist "%EXPORT_PRESETS%" (
    echo [ERROR] export_presets.cfg no encontrado en: %EXPORT_PRESETS%
    pause
    exit /b 1
)

if not exist "%PROJECT%" (
    echo [ERROR] project.godot no encontrado en: %PROJECT%
    pause
    exit /b 1
)

if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"

echo [1/3] Exportando APK desde Godot...
echo Proyecto : %PROJECT%
echo Preset    : Android (preset.1)
echo Salida    : %DIST_DIR%\%APK_NAME%
echo.

"%GODOT%" --headless --path "%AURA_ROOT%godot" --export-debug "Android" "%DIST_DIR%\%APK_NAME%"

if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la exportacion.
    echo Verifica que tengas instalado:
    echo - Android SDK en %%LOCALAPPDATA%%\Android\Sdk
    echo - NDK r25+ en %%LOCALAPPDATA%%\Android\Sdk\ndk
    echo - Java JDK 17+
    pause
    exit /b 1
)

echo.
echo [2/3] Verificando APK...
if exist "%DIST_DIR%\%APK_NAME%" (
    echo [OK] APK generada: %DIST_DIR%\%APK_NAME%
) else (
    echo [ERROR] No se encontro la APK generada.
    pause
    exit /b 1
)

echo.
echo [3/3] Instalacion en dispositivo conectado...
set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
if exist "%ADB%" (
    "%ADB%" devices
    echo.
    set /p INSTALL="Instalar APK en dispositivo? (s/N): "
    if /i "%INSTALL%"=="s" (
        echo Instalando...
        "%ADB%" install -r "%DIST_DIR%\%APK_NAME%"
        echo.
        echo [OK] Instalacion finalizada.
    ) else (
        echo Omitiendo instalacion.
    )
) else (
    echo [SKIP] ADB no encontrado en: %ADB%
    echo Conecta un dispositivo y ejecuta:
    echo   adb install -r "%DIST_DIR%\%APK_NAME%"
)

echo.
echo ==========================================
echo   Build completado
echo ==========================================
pause
endlocal
