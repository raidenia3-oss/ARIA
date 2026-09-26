@echo off
REM AURA AI Training — Quick Start (Windows)
REM Flujo completo: descargar modelo PC -> deploy a Termux -> entrenar en celular

set MODEL=qwen-1.5b
set TERMUX_MODEL=qwen-0.5b
set PYTHON=python

echo.
echo ==================================================
echo   AURA AI Training Quick Start
echo ==================================================
echo.
echo Paso 1: Descargar modelo ligero en PC (%MODEL%)
echo --------------------------------------------------
%PYTHON% scripts/setup_pc_training.py --model %MODEL% --download-only

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Fallo descarga de modelo
    pause
    exit /b 1
)

echo.
echo Paso 2: Diagnosticar conexion SSH a Termux
echo --------------------------------------------------
.\scripts\termux-connect.ps1 -Test
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: SSH no conecta. Ejecuta primero:
    echo   .\scripts\termux-connect.ps1 -Diagnose
    echo   .\scripts\termux-connect.ps1 -Menu
    pause
    exit /b 1
)

echo.
echo Paso 3: Deploy modelo + datos + trainer a Termux
echo --------------------------------------------------
%PYTHON% scripts/deploy_termux_ai.py --model %TERMUX_MODEL% --model-dir models deploy

echo.
echo Paso 4: Entrenar on-device en el celular
echo --------------------------------------------------
%PYTHON% scripts/deploy_termux_ai.py --model %TERMUX_MODEL% --model-dir models train --epochs 1 --lr 0.00005 --download-result

echo.
echo ==================================================
echo   Workflow completado
echo ==================================================
echo.
echo Modelo PC:   models/%MODEL%/
echo Modelo cell: ~/AME_AI/models/%TERMUX_MODEL%/
echo Entrenado:   termux-trained-output/
echo.
pause
