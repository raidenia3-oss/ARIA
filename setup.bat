@echo off
chcp 65001 >nul
title AURA - Setup Autónomo
echo.
echo ==========================================
echo   AURA - Configuracion Autonoma
echo ==========================================
echo.
echo Este script se ejecuta UNA SOLA VEZ.
echo Despues de esto, AURA funcionara sin intervencion humana.
echo.

:: Check if already configured
if exist ".aura\config.json" (
    echo [INFO] AURA ya esta configurado.
    echo Si quieres reconfigurar, borra .aura\config.json y ejecuta de nuevo.
    pause
    exit /b 0
)

:: Create config directory
if not exist ".aura" mkdir .aura

echo [1/6] Configuracion de Fly.io...
set /p FLY_TOKEN="Fly.io API token (enter para omitir cloud): "

echo.
echo [2/6] Configuracion de Discord...
set /p DISCORD_TOKEN="Discord Bot Token (enter para omitir): "
set /p DISCORD_CLIENT_ID="Discord Client ID (enter para omitir): "
set /p DISCORD_GUILD_ID="Discord Guild ID (enter para omitir): "

echo.
echo [3/6] Guardando configuracion...
(
echo {
echo   "fly_token": "%FLY_TOKEN%",
echo   "discord_token": "%DISCORD_TOKEN%",
echo   "discord_client_id": "%DISCORD_CLIENT_ID%",
echo   "discord_guild_id": "%DISCORD_GUILD_ID%",
echo   "backend_cloud_url": "",
echo   "setup_completed": false,
echo   "backend_deployed": false,
echo   "bot_deployed": false,
echo   "created_at": "%date% %time%"
echo }
) > .aura\config.json

echo [OK] Configuracion guardada en .aura\config.json

echo.
echo [4/6] Verificando Fly CLI...
where flyctl >nul 2>&1
if errorlevel 1 (
    echo [ERROR] flyctl no encontrado. Instalalo con: powershell -Command "iwr https://fly.io/install.ps1 -UseBasicParsing | iex"
    pause
    exit /b 1
)
echo [OK] flyctl encontrado

echo.
echo [5/6] Deploy en Fly.io...
if "%FLY_TOKEN%"=="" (
    echo [SKIP] Fly.io deploy omitido (no hay token)
) else (
    echo  Deploying backend...
    cd backend
    flyctl auth token create -n aura-deploy --duration 9999h >nul 2>&1
    flyctl apps create aura-backend >nul 2>&1
    flyctl volumes create aura_models --size 2 --region iad >nul 2>&1
    flyctl secrets set AURA_API_KEY=dev-key-random --app aura-backend >nul 2>&1
    flyctl secrets set AURA_LOCAL_MODEL_PATH="/app/models/qwen-0.5b" --app aura-backend >nul 2>&1
    flyctl secrets set AURA_CORS_ORIGINS="*" --app aura-backend >nul 2>&1
    flyctl deploy --app aura-backend
    cd ..
    
    for /f "delims=" %%i in ('flyctl info --app aura-backend --json ^| findstr "Hostname"') do (
        set BACKEND_URL=%%i
    )
    set BACKEND_URL=https://%BACKEND_URL:"Hostname":"=%
    
    echo [OK] Backend deployed: %BACKEND_URL%
    
    echo.
    if not "%DISCORD_TOKEN%"=="" (
        echo [6/6] Deploy Discord bot...
        cd services\discord-bot
        flyctl apps create aura-discord-bot >nul 2>&1
        flyctl secrets set DISCORD_BOT_TOKEN=%DISCORD_TOKEN% --app aura-discord-bot >nul 2>&1
        flyctl secrets set DISCORD_CLIENT_ID=%DISCORD_CLIENT_ID% --app aura-discord-bot >nul 2>&1
        flyctl secrets set DISCORD_GUILD_ID=%DISCORD_GUILD_ID% --app aura-discord-bot >nul 2>&1
        flyctl secrets set AURA_BACKEND_URL=%BACKEND_URL% --app aura-discord-bot >nul 2>&1
        flyctl deploy --app aura-discord-bot
        cd ..\..
        echo [OK] Discord bot deployed!
    ) else (
        echo [SKIP] Discord bot omitido (no hay credenciales)
    )
)

echo.
echo ==========================================
echo   SETUP COMPLETO
echo ==========================================
echo.
echo AURA ahora funciona de forma autonoma.
echo.
echo Proximos pasos (solo una vez):
echo   1. Build Android: dist\Build_Android.bat
echo   2. Probar backend: %BACKEND_URL%/health
echo   3. Probar Discord: /chat en tu servidor
echo.
pause
