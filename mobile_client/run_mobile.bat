@echo off
echo ========================================
echo   AURA Mobile Client - Flet
echo ========================================
echo.
echo Verificando instalacion de Flet...
python -c "import flet" 2>nul
if errorlevel 1 (
    echo Flet no encontrado. Instalando...
    pip install -r mobile_client\requirements.txt
) else (
    echo Flet ya instalado.
)
echo.
echo Iniciando cliente movil...
cd /d "%~dp0.."
python mobile_client\app.py
pause
