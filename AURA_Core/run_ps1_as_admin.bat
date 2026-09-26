@echo off
:: AURA Run PowerShell Script as Admin - Ejecuta un script de PowerShell con permisos de administrador
:: Este script abre PowerShell con permisos elevados para ejecutar el script de configuración

:: Verificar si el script de PowerShell existe
if not exist "%~dp0setup_backup_task.ps1" (
    echo Error: El script setup_backup_task.ps1 no existe en %~dp0
    pause
    exit /b 1
)

:: Verificar si estamos ejecutando como administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Este script necesita permisos de administrador.
    echo Intentando elevar privilegios...

    :: Usar PowerShell para ejecutar el script con permisos elevados
    powershell -Command "Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File \"%~dp0setup_backup_task.ps1\"' -Verb RunAs"
    exit /b 0
)

:: Ejecutar el script de PowerShell con permisos de administrador
echo Ejecutando setup_backup_task.ps1 con permisos de administrador...
powershell -ExecutionPolicy Bypass -File "%~dp0setup_backup_task.ps1"

echo.
echo Configuración completada.
pause