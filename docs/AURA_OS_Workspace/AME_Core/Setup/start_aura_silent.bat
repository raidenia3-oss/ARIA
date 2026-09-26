@echo off
:: Script para iniciar AURA de forma silenciosa usando PM2
:: Este script se ejecutará en segundo plano sin abrir ventanas de CMD

:: Verificar si PM2 está instalado
where pm2 >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: PM2 no está instalado. Instálalo con: npm install pm2 -g
    pause
    exit /b 1
)

:: Verificar si el script de AURA existe
set AURA_SCRIPT=%~dp0..\AURA_Core\crash_overseer.py
if not exist "%AURA_SCRIPT%" (
    echo Error: Script de AURA no encontrado en %AURA_SCRIPT%
    pause
    exit /b 1
)

:: Iniciar PM2 en modo silencioso
echo Iniciando AURA en modo silencioso...
pm2 resurrect
pm2 start %AURA_SCRIPT% --silent --name "AURA Stealth Mode"

:: Verificar si AURA se inició correctamente
pm2 list | find "AURA Stealth Mode" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo ✅ AURA iniciado correctamente en modo silencioso.
    exit /b 0
) else (
    echo ❌ Error al iniciar AURA.
    exit /b 1
)