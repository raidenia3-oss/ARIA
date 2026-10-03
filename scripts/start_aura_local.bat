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
:: Objetivo verificado: el entrypoint real es ARIA_APP\backend\app.py servido como
:: "app:app" con cwd en ARIA_APP\backend, el mismo modulo y directorio que lanza
:: v5/electron/main.ts:111. Antes apuntaba a ame_backend.src.main:app, que NO
:: existe: ame_backend/ solo contiene .env.local.
echo.
echo [2/4] Iniciando Backend AURA (FastAPI puerto 8000)...
if not exist "%AURA_ROOT%\ARIA_APP\backend\app.py" (
    echo [ERROR] No existe "%AURA_ROOT%\ARIA_APP\backend\app.py".
    echo         El entrypoint de ARIA v5 es ARIA_APP\backend\app.py, servido
    echo         como "app:app" desde ARIA_APP\backend.
    echo         No se arranca nada. Abortando.
    pause
    exit /b 1
)
pushd "%AURA_ROOT%\ARIA_APP\backend"
start "AURA Backend" cmd /c "%PYTHON% -m uvicorn app:app --host 0.0.0.0 --port 8000"
popd
set /a _AURA_WAIT=0
echo       Esperando backend...
:wait_backend
curl -s http://localhost:8000/health >nul 2>&1
if not errorlevel 1 goto backend_ready
timeout /t 2 /nobreak >nul
set /a _AURA_WAIT+=1
if %_AURA_WAIT% GEQ 60 goto backend_timeout
goto wait_backend
:backend_ready
echo       [OK] Backend corriendo en http://localhost:8000
goto backend_done
:backend_timeout
echo [ERROR] El backend no respondio en /health tras 120 s.
echo         Revisa la ventana "AURA Backend" para ver el trace de uvicorn.
echo         Abortando en vez de dejar un bucle infinito sin salida.
pause
exit /b 1
:backend_done

:: Iniciar AURA Core Agent (usa Jan, no Ollama)
:: El "cd /d" no se comprobaba: si fallaba, "start" abria una ventana que moria al
:: instante y el script imprimia "[OK] AURA Core iniciado" sin haber arrancado nada.
:: Se verifica el directorio y el modulo antes de afirmar que arranco.
echo.
echo [3/4] Iniciando AURA Core Agent...
set "CORE_DIR=%AURA_ROOT%\docs\AURA_OS_Workspace\AME_Core\AURA_Core"
if not exist "%CORE_DIR%\aura_core.py" (
    echo [ERROR] No existe "%CORE_DIR%\aura_core.py".
    echo         No se arranca nada. Abortando.
    pause
    exit /b 1
)
pushd "%CORE_DIR%"
start "AURA Core" cmd /c "%PYTHON% aura_core.py"
popd
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
