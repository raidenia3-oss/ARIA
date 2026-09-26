@echo off
:: AURA Backup Task Setup - Script para configurar tarea programada en Windows
:: Configura un backup semanal automático del sistema AURA

:: Configuración
set SCRIPT_DIR=%~dp0
set BACKUP_SCRIPT=backup_system.py
set TASK_NAME=AURA_Weekly_Backup
set TASK_DESCRIPTION=Backup semanal automático del sistema AURA
set TASK_DAY=SUN
set TASK_TIME=00:00

:: Verificar si el script de backup existe
if not exist "%SCRIPT_DIR%\%BACKUP_SCRIPT%" (
    echo Error: Script de backup "%BACKUP_SCRIPT%" no encontrado en %SCRIPT_DIR%
    exit /b 1
)

:: Verificar si el script es ejecutable
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Python no está disponible en el PATH
    exit /b 1
)

:: Verificar si la tarea ya existe
schtasks /query /tn "%TASK_NAME%" /fo csv 2>nul | findstr /i "%TASK_NAME%" >nul
if %ERRORLEVEL% equ 0 (
    echo La tarea "%TASK_NAME%" ya existe. Verificando...
    goto :verify_task
)

:: Crear la tarea programada
echo Configurando tarea programada "%TASK_NAME%"...
schtasks /create /tn "%TASK_NAME%" /tr "%SCRIPT_DIR%python %BACKUP_SCRIPT% backup" /sc weekly /d %TASK_DAY% /st %TASK_TIME% /ru SYSTEM /f

if %ERRORLEVEL% equ 0 (
    echo Tarea programada creada con éxito: %TASK_NAME%
    echo Descripción: %TASK_DESCRIPTION%
    echo Programación: Cada domingo a las %TASK_TIME%
    echo Comando: python "%SCRIPT_DIR%%BACKUP_SCRIPT%" backup
    goto :verify_task
) else (
    echo Error: No se pudo crear la tarea programada
    exit /b 1
)

:verify_task
echo Verificando tarea programada...
schtasks /query /tn "%TASK_NAME%" /fo csv 2>nul | findstr /i "%TASK_NAME%" >nul
if %ERRORLEVEL% equ 0 (
    echo Tarea verificada: %TASK_NAME%
    schtasks /query /tn "%TASK_NAME%" /v
) else (
    echo Error: No se pudo verificar la tarea programada
    exit /b 1
)

echo.
echo Configuración completada con éxito.
echo La tarea "%TASK_NAME%" se ejecutará cada domingo a las %TASK_TIME%.
echo.
echo Para verificar el estado de la tarea, usa:
echo schtasks /query /tn "%TASK_NAME%"
echo.
echo Para eliminar la tarea, usa:
echo schtasks /delete /tn "%TASK_NAME%" /f