@echo off
title AURA - Cloudflare Tunnel Setup
color 0A
cls
echo ======================================================
echo      🌐 AURA - CLOUDFLARE TUNNEL SETUP
echo      Exponer Shadow-Core de forma segura
echo ======================================================
echo.
echo [1/4] Verificando cloudflared...
echo.

where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] cloudflared no encontrado. Instalando...
    echo.
    echo Descargando cloudflared desde Cloudflare...
    curl -sL -o "%TEMP%\cloudflared.msi" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.msi
    if exist "%TEMP%\cloudflared.msi" (
        msiexec /i "%TEMP%\cloudflared.msi" /quiet /norestart
        echo [✔] cloudflared instalado correctamente
    ) else (
        echo [✕] Error: No se pudo descargar cloudflared
        echo.
        echo Descarga manual: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
        pause
        exit /b 1
    )
) else (
    for /f "tokens=*" %%i in ('cloudflared --version') do echo [✔] %%i
)

echo.
echo [2/4] Autenticando con Cloudflare...
echo.
echo Nota: Se abrira una ventana del navegador para autenticarte.
echo Si no tienes cuenta, crea una en https://dash.cloudflare.com/sign-up
echo.
cloudflared tunnel login
if %errorlevel% neq 0 (
    echo [✕] Error en autenticacion. Intenta de nuevo.
    pause
    exit /b 1
)
echo [✔] Autenticacion exitosa

echo.
echo [3/4] Creando tunel para AURA...
echo.
set TUNNEL_NAME=aura-shadow-core

cloudflared tunnel create %TUNNEL_NAME% >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] El tunel ya existe. Usando tunel existente.
)

echo.
echo Obteniendo ID del tunel...
for /f "tokens=*" %%i in ('cloudflared tunnel list ^| findstr "%TUNEL_NAME%"') do set TUNNEL_LINE=%%i
echo [✔] Tunel configurado

echo.
echo [4/4] Creando archivo de configuracion...
echo.

set CONFIG_FILE="%USERPROFILE%\.cloudflared\config_aura.yml"
(
echo tunnel: %TUNEL_NAME%
echo credentials-file: %USERPROFILE%\.cloudflared\%TUNEL_NAME%.json
echo.
echo ingress:
echo   - hostname: aura-dashboard.*.trycloudflare.com
echo     service: http://localhost:5000
echo   - hostname: aura-api.*.trycloudflare.com
echo     service: http://localhost:5001
echo   - hostname: aura-feed.*.trycloudflare.com
echo     service: http://localhost:5002
echo   - hostname: aura-executor.*.trycloudflare.com
echo     service: http://localhost:5003
echo   - service: http_status:404
) > %CONFIG_FILE%

echo [✔] Configuracion creada en %CONFIG_FILE%
echo.
echo ======================================================
echo      🚀 TUNEL LISTO PARA INICIAR
echo ======================================================
echo.
echo Para iniciar el tunel manualmente:
echo   cloudflared tunnel run %TUNEL_NAME%
echo.
echo Para iniciar con configuracion personalizada:
echo   cloudflared tunnel --config %CONFIG_FILE% run
echo.
echo Para iniciar AURA con tunel automatico:
echo   start_aura_with_tunnel.bat
echo.
echo ======================================================
echo.
echo ¿Deseas iniciar el tunel ahora? (S/N)
set /p START_NOW=
if /i "%START_NOW%"=="S" (
    echo Iniciando tunel Cloudflare para AURA...
    start "AURA-Tunnel" cmd /c "cloudflared tunnel run %TUNEL_NAME%"
    echo [✔] Tunel iniciado en ventana separada
    echo.
    echo Para ver la URL publica, revisa los logs del tunel.
    echo Tipicamente aparecera como: https://%TUNEL_NAME%.trycloudflare.com
)

echo.
echo ======================================================
echo      ✅ SETUP COMPLETADO
echo ======================================================
echo.
echo Scripts utiles:
echo   - Setup/start_aura_with_tunnel.bat  (Inicia AURA + Tunel)
echo   - Setup/stop_aura_tunnel.bat        (Detiene el tunel)
echo.
pause