@echo off
title AURA Ecosystem - Inicio Completo
color 0A
echo ============================================
echo   AURA ECOSYSTEM - Inicio Completo
echo   %date% %time%
echo ============================================
echo.

set "AURA_ROOT=C:\Users\User\Downloads\AURA"

cd /d "%AURA_ROOT%"

:: Verificar entorno virtual
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Entorno virtual .venv no encontrado.
    echo Ejecuta: python -m venv .venv
    echo Luego: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo [OK] Entorno virtual detectado.
echo [OK] Iniciando pipeline de deploy...
echo.

:: Ejecutar pipeline de deploy
".venv\Scripts\python.exe" -X utf8 core/deploy_pipeline.py

echo.
echo ============================================
echo   Pipeline finalizado.
echo ============================================
pause
