@echo off
:: Script para iniciar AURA con Cloudflare Tunnel
:: 1. Inicia el servidor Flask
:: 2. Configura y ejecuta el túnel Cloudflare
:: 3. Muestra la URL pública generada

echo ===================================================
echo 🌐 Iniciando AURA con Cloudflare Tunnel
echo ===================================================

:: Iniciar el servidor Flask en segundo plano
start "Flask Server" cmd /c "python AME_Core\servidor_ame.py"

:: Esperar a que el servidor esté listo
timeout /t 10 >nul

:: Configurar y ejecutar el túnel Cloudflare
echo Configurando túnel Cloudflare...
cd /d %~dp0
cd ..\cloudflared

:: Verificar si cloudflared está instalado
where cloudflared >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ❌ cloudflared no está instalado. Instálalo manualmente desde:
    echo https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/tunnel-guide/
    pause
    exit /b 1
)

:: Iniciar el túnel
echo Iniciando túnel Cloudflare...
echo Usa las credenciales: admin / AURA2024!
cloudflared tunnel run aura-tunnel

:: Si el túnel se cierra, reiniciarlo automáticamente
:loop
timeout /t 5 >nul
where cloudflared >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ⚠️  cloudflared se cerró. Reiniciando...
    cloudflared tunnel run aura-tunnel
    goto loop
)