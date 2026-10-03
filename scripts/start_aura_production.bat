@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ============================================
echo   AURA Production - Inicio
echo ============================================

:: 1) Verificar Ollama
echo.
echo [1/4] Verificando Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Ollama no encontrado en PATH. Instala Ollama primero.
    pause
    exit /b 1
)

echo [OK] Ollama encontrado.

:: Verificar que el modelo qwen2.5:0.5b este disponible
ollama list | findstr /i "qwen2.5:0.5b" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Modelo qwen2.5:0.5b no encontrado. Descargando...
    ollama pull qwen2.5:0.5b
    if errorlevel 1 (
        echo [ERROR] No se pudo descargar qwen2.5:0.5b
        pause
        exit /b 1
    )
)

echo [OK] Modelo qwen2.5:0.5b disponible.

:: 2) Iniciar backend FastAPI
:: Objetivo verificado: el entrypoint real es ARIA_APP\backend\app.py servido como
:: "app:app" con cwd en ARIA_APP\backend, el mismo modulo y directorio que lanza
:: v5/electron/main.ts:111. Antes apuntaba a ame_backend.src.main:app, que NO
:: existe: ame_backend/ solo contiene .env.local.
echo.
echo [2/4] Iniciando backend FastAPI...

:: Resolver la raiz del repo a partir de la ubicacion de este script, para que el
:: objetivo no dependa del cwd desde el que se invoque.
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "AURA_ROOT=%%~fI"

set "BACKEND_DIR=%AURA_ROOT%\ARIA_APP\backend"
if not exist "%BACKEND_DIR%\app.py" (
    echo [ERROR] No existe "%BACKEND_DIR%\app.py".
    echo         El entrypoint de ARIA v5 es ARIA_APP\backend\app.py, servido
    echo         como "app:app" desde ARIA_APP\backend.
    echo         No se arranca nada. Abortando.
    pause
    exit /b 1
)

set "PYTHONPATH=%BACKEND_DIR%"
set "PID_FILE_BACKEND=%TEMP%\aura_backend.pid"

pushd "%BACKEND_DIR%"
start "AURA Backend" /B python -m uvicorn app:app --host 0.0.0.0 --port 8000
popd

:: Verificar de verdad en vez de asumir: antes se imprimia "[OK] Backend
:: iniciado" tras 3 s fijos sin comprobar nada.
set /a _AURA_WAIT=0
:wait_backend
curl -s http://localhost:8000/health >nul 2>&1
if not errorlevel 1 goto backend_ready
timeout /t 1 /nobreak >nul
set /a _AURA_WAIT+=1
if %_AURA_WAIT% GEQ 60 goto backend_timeout
goto wait_backend
:backend_ready
echo [OK] Backend iniciado y respondiendo en http://localhost:8000
goto backend_done
:backend_timeout
echo [ERROR] El backend no respondio en /health tras 60 s. No se puede marcar
echo         como iniciado. Revisa la salida de uvicorn.
pause
exit /b 1
:backend_done

:: 3) Ejecutar dashboard una vez
echo.
echo [3/4] Mostrando estado inicial...
:: Ruta absoluta: tras el popd el cwd es el de invocacion, no necesariamente la raiz.
python "%AURA_ROOT%\training\scripts\dashboard.py"

:: 4) Guardar informacion de procesos
echo.
echo [4/4] Guardando informacion de procesos...
echo Backend iniciado en: %DATE% %TIME% > "%PID_FILE_BACKEND%.info"
echo URL: http://localhost:8000 >> "%PID_FILE_BACKEND%.info"
echo Health: http://localhost:8000/health >> "%PID_FILE_BACKEND%.info"

echo.
echo ============================================
echo   AURA Production - Iniciado
echo ============================================
echo Backend: http://localhost:8000
echo Health:  http://localhost:8000/health
echo.
echo Para detener: scripts\stop_aura_production.bat
echo ============================================

pause