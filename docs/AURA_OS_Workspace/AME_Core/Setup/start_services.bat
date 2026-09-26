@echo off
cd /d "c:\Users\User\Downloads\AURA"
setlocal enabledelayedexpansion

:: ============================================================
:: AURA Auto-Resilience Startup Script
:: ============================================================
echo ============================================
echo   AURA — Starting Services
echo ============================================

:: 1. Iniciar Ollama en segundo plano
echo [1/5] Starting Ollama...
start /b "" "ollama serve"
echo       Ollama launched in background

:: 2. WAIT: Esperar a que Ollama responda (check_health.py)
echo [2/5] Waiting for Ollama to be ready...
python AURA_Core\check_health.py
if %errorlevel% neq 0 (
    echo [WARNING] Ollama health check timed out, continuing anyway...
) else (
    echo       Ollama is RESPONDING
)

:: 3. Iniciar Núcleo de AURA
echo [3/5] Starting AURA Core...
start /b "" python AURA_Core\aura_core.py
echo       AURA Core launched

:: 4. Iniciar Webhook Server (puerto 5001)
echo [4/5] Starting AURA Webhook...
start /b "" python AURA_Core\aura_webhook.py
echo       Webhook launched on port 5001

:: 5. Iniciar Servidor Flask / Dashboard (puerto 5000)
echo [5/5] Starting AME Dashboard Server...
start /b "" python AME_Core\servidor_ame.py
echo       Dashboard launched on port 5000

echo.
echo ============================================
echo   ALL SERVICES STARTED
echo   Dashboard: http://localhost:5000
echo   Webhook:   http://localhost:5001
echo   Ollama:    http://localhost:11434
echo ============================================
endlocal
exit