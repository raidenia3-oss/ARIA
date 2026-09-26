@echo off
setlocal

echo ============================================
echo   AURA Full Stack - Detencion
echo ============================================

echo.
echo Deteniendo procesos de AURA...

:: Detener procesos por titulo
tasklist /FI "WINDOWTITLE eq AURA Backend*" 2>nul | findstr /I "python.exe" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Deteniendo AURA Backend...
    taskkill /FI "WINDOWTITLE eq AURA Backend*" /F >nul 2>&1
) else (
    echo [INFO] No se encontro proceso AURA Backend.
)

tasklist /FI "WINDOWTITLE eq AURA Frontend*" 2>nul | findstr /I "node.exe" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Deteniendo AURA Frontend...
    taskkill /FI "WINDOWTITLE eq AURA Frontend*" /F >nul 2>&1
) else (
    echo [INFO] No se encontro proceso AURA Frontend.
)

:: Intentar detener por puertos
netstat -ano | findstr ":8000.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
        echo [INFO] Deteniendo proceso en puerto 8000 (PID %%a)...
        taskkill /F /PID %%a >nul 2>&1
    )
)

netstat -ano | findstr ":3000.*LISTENING" >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000.*LISTENING"') do (
        echo [INFO] Deteniendo proceso en puerto 3000 (PID %%a)...
        taskkill /F /PID %%a >nul 2>&1
    )
)

echo.
echo [OK] Procesos detenidos.
echo ============================================
pause