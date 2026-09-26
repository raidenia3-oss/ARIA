@echo off
setlocal ENABLEDELAYEDEXPANSION

echo ============================================
echo   AURA Full Stack - Inicio
echo ============================================

:: 1) Verificar Ollama
echo.
echo [1/5] Verificando Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Ollama no encontrado en PATH.
    pause
    exit /b 1
)

echo [OK] Ollama encontrado.
ollama list | findstr /i "qwen2.5:0.5b" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Descargando qwen2.5:0.5b...
    ollama pull qwen2.5:0.5b
)
echo [OK] Modelo qwen2.5:0.5b disponible.

:: 2) Iniciar backend FastAPI
echo.
echo [2/5] Iniciando backend FastAPI...
set "PYTHONPATH=%CD%"
start "AURA Backend" /B python -m uvicorn ame_backend.src.main:app --host 0.0.0.0 --port 8000
timeout /t 4 /nobreak >nul
echo [OK] Backend en http://localhost:8000

:: 3) Iniciar frontend Next.js
echo.
echo [3/5] Iniciando frontend Next.js...
if exist frontend\package.json (
    cd frontend
    start "AURA Frontend" /B npm run dev
    cd ..
    echo [OK] Frontend iniciado en http://localhost:3000
) else (
    echo [WARN] frontend/package.json no encontrado, omitiendo frontend.
)

:: 4) Mostrar dashboard inicial
echo.
echo [4/5] Estado inicial del sistema...
python training\scripts\dashboard.py

:: 5) Guardar info de procesos
echo.
echo [5/5] Guardando informacion de procesos...
echo Backend: http://localhost:8000 > "%TEMP%\aura_fullstack.info"
echo Frontend: http://localhost:3000 >> "%TEMP%\aura_fullstack.info"
echo Health: http://localhost:8000/health >> "%TEMP%\aura_fullstack.info"
echo Iniciado: %DATE% %TIME% >> "%TEMP%\aura_fullstack.info"

echo.
echo ============================================
echo   AURA Full Stack - Iniciado
echo ============================================
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo Health:  http://localhost:8000/health
echo.
echo Para detener: scripts\stop_aura_full.bat
echo ============================================

pause