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
echo.
echo [2/4] Iniciando backend FastAPI...
set "PYTHONPATH=%CD%"
set "PID_FILE_BACKEND=%TEMP%\aura_backend.pid"

start "AURA Backend" /B python -m uvicorn ame_backend.src.main:app --host 0.0.0.0 --port 8000
timeout /t 3 /nobreak >nul

echo [OK] Backend iniciado en http://localhost:8000

:: 3) Ejecutar dashboard una vez
echo.
echo [3/4] Mostrando estado inicial...
python training\scripts\dashboard.py

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