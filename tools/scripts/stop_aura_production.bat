@echo off
setlocal

echo ============================================
echo   AURA Production - Detencion
echo ============================================

echo.
echo Deteniendo procesos de AURA...

:: Detener procesos python que ejecutan uvicorn con ame_backend.src.main
tasklist /FI "WINDOWTITLE eq AURA Backend*" /FI "IMAGENAME eq python.exe" 2>nul | findstr /I "python.exe" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Detectado proceso AURA Backend. Deteniendo...
    taskkill /FI "WINDOWTITLE eq AURA Backend*" /F >nul 2>&1
) else (
    echo [INFO] No se encontro proceso con titulo 'AURA Backend'.
)

:: Intentar detener por puerto 8000
netstat -ano | findstr ":8000.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
        echo [INFO] Deteniendo proceso en puerto 8000 (PID %%a)...
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo.
echo [OK] Procesos detenidos.
echo ============================================
pause