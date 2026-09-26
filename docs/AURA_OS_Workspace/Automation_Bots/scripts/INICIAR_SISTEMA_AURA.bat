@echo off
title AURA SYSTEM LAUNCH v1.0
color 0B

echo ==========================================
echo    INICIANDO SISTEMA AURA - PRODUCCION
echo ==========================================
echo.

:: ── 1. Detectar IP Local ──
echo [1/6] Detectando IP local...
for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /R "^[[:space:]]*IPv4"') do set "LOCAL_IP=%%i"
set LOCAL_IP=%LOCAL_IP: =%
if "%LOCAL_IP%"=="" (
    for /f "tokens=2 delims=:" %%i in ('ipconfig ^| findstr /R "^[[:space:]]*Direcci.n IPv4"') do set "LOCAL_IP=%%i"
    set LOCAL_IP=%LOCAL_IP: =%
)
if "%LOCAL_IP%"=="" set LOCAL_IP=192.168.1.100
echo    IP Detectada: %LOCAL_IP%
echo.

:: ── 2. Verificar Java (necesario para Gradle/APK) ──
echo [2/6] Verificando Java...
java -version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    for /f "tokens=3" %%g in ('java -version 2^>^&1 ^| findstr /i "version"') do set JAVA_VER=%%g
    set JAVA_VER=%JAVA_VER:"=%
    echo    Java detectado: %JAVA_VER%
) else (
    echo    ⚠️  Java no encontrado (solo se necesita para compilar APK)
)
echo.

:: ── 3. Verificar APK para OTA ──
echo [3/6] Verificando APK OTA...
if exist AME_PROD.apk (
    for %%f in (AME_PROD.apk) do set APK_SIZE=%%~zf
    set /a APK_SIZE_MB=%APK_SIZE% / 1048576
    echo    APK disponible: AME_PROD.apk (%APK_SIZE_MB% MB)
) else (
    echo    ⚠️  APK no encontrado. Compila primero con COMPILAR_AME_FINAL.bat
)
echo.

:: ── 4. Verificar dependencias Python ──
echo [4/6] Verificando dependencias Python...
if exist env\Scripts\python.exe (
    set PYTHON=env\Scripts\python.exe
    echo    Usando entorno virtual: env\
) else (
    set PYTHON=python
    echo    Usando Python del sistema
)
echo.

:: ── 5. Iniciar Servidor AURA (puerto 5000) ──
echo [5/6] Iniciando Servidor AURA Command Center...
echo    Host: 0.0.0.0:5000
echo    Dashboard: http://%LOCAL_IP%:5000/
echo    OTA APK:   http://%LOCAL_IP%:5000/api/descargar-ame
echo.
start "AURA-Server" cmd /k "cd /d %~dp0 && title AURA Server [Puerto 5000] && color 0A && %PYTHON% AME_Core/servidor_ame.py"

:: Esperar 3 segundos para que el servidor inicie
timeout /t 3 /nobreak >nul

:: ── 6. Verificar servidor ──
echo [6/6] Verificando que el servidor responda...
powershell -Command "& { try { $r = Invoke-WebRequest -Uri 'http://localhost:5000/api/status' -UseBasicParsing -TimeoutSec 5; if ($r.StatusCode -eq 200) { Write-Host '    ✅ Servidor AURA respondiendo OK' -ForegroundColor Green } } catch { Write-Host '    ⚠️  Servidor no responde aun (puede tardar unos segundos)' -ForegroundColor Yellow } }"

echo.
echo ==========================================
echo   SISTEMA AURA ACTIVO
echo ==========================================
echo.
echo   Arquitecto, ingrese desde su celular a:
echo   🌐 http://%LOCAL_IP%:5000/
echo.
echo   Para descargar AME en su celular:
echo   📱 http://%LOCAL_IP%:5000/api/descargar-ame
echo.
echo   Para ver estado del servidor:
echo   🔧 http://localhost:5000/api/status
echo.
echo ==========================================
echo   Presione cualquier tecla para cerrar
echo   esta ventana (el servidor seguira activo)
echo ==========================================
pause >nul