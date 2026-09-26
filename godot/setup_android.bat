@echo off
setlocal
chcp 65001 >nul
title AURA - Setup Android Build

set "AURA_ROOT=%~dp0..\"
set "SDK=%LOCALAPPDATA%\Android\Sdk"
set "NDK_DIR=%SDK%\ndk\25.1.8937393"
set "CMD_LINE_TOOLS=%SDK%\cmdline-tools\latest\bin\sdkmanager.bat"

echo ==========================================
echo   AURA - Android Setup
echo ==========================================
echo.

if not exist "%SDK%" (
    echo [ERROR] Android SDK no encontrado en: %SDK%
    echo Instala Android Studio y el SDK.
    pause
    exit /b 1
)

echo [1/4] Verificando Android SDK...
echo SDK: %SDK%
if exist "%SDK%\platform-tools\adb.exe" (
    echo [OK] platform-tools encontrado
) else (
    echo [ERROR] platform-tools no encontrado en SDK
    pause
    exit /b 1
)

echo.
echo [2/4] Verificando NDK...
if exist "%NDK_DIR%" (
    echo [OK] NDK encontrado: %NDK_DIR%
) else (
    echo [WARN] NDK no encontrado en: %NDK_DIR%
    echo Godot 4.x requiere NDK r25+ para exportar a Android.
    echo.
    echo Opciones:
    echo 1. Instalar Android Studio ^> SDK Manager ^> NDK ^(Side-by-side^)
    echo 2. Descargar NDK manualmente desde:
    echo    https://developer.android.com/studio#downloads
    echo.
    echo Si usas sdkmanager, ejecuta:
    echo   sdkmanager "ndk;25.1.8937393"
    echo.
    pause
)

echo.
echo [3/4] Verificando Java...
java -version 2>&1 | findstr "version" >nul
if errorlevel 1 (
    echo [ERROR] Java no encontrado. Instala JDK 17 o 21.
    pause
    exit /b 1
) else (
    echo [OK] Java detectado
)

echo.
echo [4/4] Verificando Godot...
set "GODOT=C:\Users\User\OneDrive\Escritorio\Godot_v4.6-stable_win64.exe"
if not exist "%GODOT%" (
    echo [ERROR] Godot no encontrado en: %GODOT%
    echo Ajusta la ruta en build_android.bat
    pause
    exit /b 1
) else (
    echo [OK] Godot encontrado
)

echo.
echo ==========================================
echo   Setup completado
echo ==========================================
echo.
echo Para buildear la APK ejecuta:
echo   godot\build_android.bat
echo.
pause
endlocal
