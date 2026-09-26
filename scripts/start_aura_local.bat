@echo off
chcp 65001 >nul
title AURA Local — Sistema Hibrido Inteligente
echo ============================================
echo   AURA LOCAL — Modo Sin Nube
echo   Jan + APIs Externas + Apps Locales
echo ============================================
echo.

set AURA_ROOT=C:\Users\User\Downloads\AURA
set PYTHON=%AURA_ROOT%\AURA_Core\venv_decision_core\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

:: Verificar que Jan este instalado
if not exist "%LOCALAPPDATA%\Programs\jan\Jan.exe" (
    echo [ERROR] Jan no esta instalado. Instalalo desde https://jan.ai/
    pause
    exit /b 1
)

:: Iniciar Jan si no esta corriendo
echo [1/4] Verificando Jan...
tasklist /FI "IMAGENAME eq Jan.exe" 2>NUL | find /I "Jan.exe" >NUL
if errorlevel 1 (
    echo       Iniciando Jan...
    start "" "%LOCALAPPDATA%\Programs\jan\Jan.exe"
    echo       Esperando que Jan este listo (puerto 1337)...
    :wait_jan
    curl -s http://localhost:1337/v1/models >nul 2>&1
    if errorlevel 1 (
        timeout /t 2 /nobreak >nul
        goto wait_jan
    )
    echo       [OK] Jan corriendo en localhost:1337
) else (
    echo       [OK] Jan ya esta corriendo
)

:: Iniciar Backend AURA (FastAPI)
echo.
echo [2/4] Iniciando Backend AURA (FastAPI puerto 8000)...
cd /d "%AURA_ROOT%"
start "AURA Backend" cmd /c "%PYTHON% -m uvicorn ame_backend.src.main:app --host 0.0.0.0 --port 8000"
echo       Esperando backend...
:wait_backend
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto wait_backend
)
echo       [OK] Backend corriendo en http://localhost:8000

:: Iniciar AURA Core Agent (usa Jan, no Ollama)
echo.
echo [3/4] Iniciando AURA Core Agent...
cd /d "%AURA_ROOT%\docs\AURA_OS_Workspace\AME_Core\AURA_Core"
start "AURA Core" cmd /c "%PYTHON% aura_core.py"
echo       [OK] AURA Core iniciado

:: Frontend Next.js (opcional)
echo.
echo [4/4] Frontend Next.js...
if exist "%AURA_ROOT%\frontend\package.json" (
    echo       Iniciando frontend en puerto 3000...
    cd /d "%AURA_ROOT%\frontend"
    start "AURA Frontend" cmd /c "npm run dev"
    echo       [OK] Frontend en http://localhost:3000
) else (
    echo       [SKIP] Frontend no encontrado, usa la API directamente
)

echo.
echo ============================================
echo   AURA LOCAL operativo.
echo.
echo   Backend API:  http://localhost:8000
echo   Hybrid Chat:  http://localhost:8000/api/hybrid/unified/process
echo   Local Apps:   http://localhost:8000/api/local/apps/status
echo   Jan API:      http://localhost:1337/v1
echo.
echo   Los servicios corren en ventanas separadas.
echo ============================================
echo.

:: Monitorear servicios
:monitor
timeout /t 30 /nobreak >nul
goto monitor
