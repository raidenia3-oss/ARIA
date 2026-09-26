@echo off
:: AURA Live Reload - Script para iniciar el sistema de recarga automática en Railway
:: Este script debe ejecutarse en el entorno de Railway para habilitar Live Reload

echo =============================================
echo AURA Live Reload System - Iniciando...
echo =============================================

:: Verificar si Python está disponible
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Python no está instalado o no está en el PATH.
    echo Por favor, asegúrate de que Python esté disponible en el entorno.
    pause
    exit /b 1
)

:: Verificar si watchdog está instalado
python -c "import watchdog" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Instalando watchdog...
    pip install watchdog
    if %ERRORLEVEL% neq 0 (
        echo Error: No se pudo instalar watchdog.
        pause
        exit /b 1
    )
)

:: Cambiar al directorio correcto
cd /d "%~dp0"

:: Iniciar el sistema de Live Reload
echo Iniciando Live Reload para monitorear cambios en AME_Core...
echo Presiona Ctrl+C para detener el sistema.

:: Ejecutar el script de Live Reload
python live_reload.py

echo =============================================
echo Sistema de Live Reload detenido.
echo =============================================