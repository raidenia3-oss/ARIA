@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ============================================
echo   AURA Local Deployment
echo ============================================

:: Verificar Docker
echo.
echo [1/5] Verificando Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker no esta instalado o no esta en PATH.
    pause
    exit /b 1
)
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose no esta disponible.
    pause
    exit /b 1
)
echo [OK] Docker y Docker Compose detectados.

:: Crear directorio de logs
if not exist logs mkdir logs
set "LOG_FILE=logs\deploy.log"
echo [INFO] Iniciando deployment en %DATE% %TIME% > "%LOG_FILE%"

:: Build
echo.
echo [2/5] Building imagenes...
docker compose build >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [ERROR] Fallo en docker compose build. Ver %LOG_FILE%
    pause
    exit /b 1
)
echo [OK] Build completado.

:: Up
echo.
echo [3/5] Levantando servicios...
docker compose up -d >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [ERROR] Fallo en docker compose up. Ver %LOG_FILE%
    pause
    exit /b 1
)
echo [OK] Servicios iniciados.

:: Esperar healthchecks
echo.
echo [4/5] Esperando healthchecks...
timeout /t 15 /nobreak >nul

:: Verificar backend
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo [WARN] Backend aun no responde en /health.
) else (
    echo [OK] Backend saludable en http://localhost:8000/health
)

:: Verificar frontend
curl -s http://localhost:3000 >nul 2>&1
if errorlevel 1 (
    echo [WARN] Frontend aun no responde en http://localhost:3000
) else (
    echo [OK] Frontend disponible en http://localhost:3000
)

:: Estado
echo.
echo [5/5] Estado de servicios:
docker compose ps

echo.
echo ============================================
echo   AURA Deployment Completado
echo ============================================
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo Health:   http://localhost:8000/health
echo.
echo Logs: %LOG_FILE%
echo ============================================

pause