@echo off
echo =============================================
echo INICIANDO SISTEMA AURA CON TÚNEL Y OTA LIVE
echo =============================================

:: Configuración del entorno
set PROJECT_DIR=C:\Users\User\Downloads\AURA
set DIST_DIR=%PROJECT_DIR%\dist
set CAPACITOR_CONFIG=%PROJECT_DIR%\dist\capacitor.config.ts
set TUNNEL_URL=https://tu-tunel-cloudflare.com

:: 1. Verificar que el túnel de Cloudflare esté corriendo
echo.
echo 1/5: Verificando túnel de Cloudflare...
if not exist "%PROJECT_DIR%\cloudflared\config.yml" (
    echo Error: No se encontró la configuración de Cloudflare.
    echo Asegúrate de ejecutar primero: Setup\setup_cloudflare_tunnel.bat
    pause
    exit /b 1
)

:: 2. Configurar capacitor.config.ts para OTA
echo.
echo 2/5: Configurando capacitor.config.ts para OTA...
(
    echo import { CapacitorConfig } from '@capacitor/cli';
    echo.
    echo const config: CapacitorConfig = {
    echo   appId: 'com.aura.mobile',
    echo   appName: 'AURA Mobile',
    echo   webDir: 'www',
    echo   server: {
    echo     androidScheme: 'https',
    echo     url: '%TUNNEL_URL%',
    echo     cleartext: true
    echo   },
    echo   plugins: {
    echo     BiometricAuth: {
    echo       // Configuración específica para el plugin de biometría
    echo     }
    echo   }
    echo };
    echo.
    echo export default config;
) > "%CAPACITOR_CONFIG%"

echo Configuración de OTA guardada en %CAPACITOR_CONFIG%

:: 3. Compilar el proyecto
echo.
echo 3/5: Compilando proyecto AME...
cd /d "%PROJECT_DIR%"
call COMPILAR_AME_FINAL.bat

if %ERRORLEVEL% neq 0 (
    echo Error al compilar el proyecto.
    pause
    exit /b 1
)

:: 4. Iniciar servidor estático para OTA
echo.
echo 4/5: Iniciando servidor estático para OTA...
cd /d "%PROJECT_DIR%\Shadow-Core"
start python static_server.py

:: 5. Iniciar túnel de Cloudflare
echo.
echo 5/5: Iniciando túnel de Cloudflare...
cd /d "%PROJECT_DIR%\cloudflared"
start cloudflared tunnel run aura-tunnel --url http://localhost:8000

echo.
echo =============================================
echo SISTEMA AURA CON OTA LIVE INICIADO
echo =============================================
echo.
echo - El APK compilado está en: %DIST_DIR%\android\app\build\outputs\apk\debug
echo - El servidor estático está corriendo en: http://localhost:8000
echo - El túnel de Cloudflare está disponible en: %TUNNEL_URL%
echo.
echo NOTA: Cualquier cambio en el frontend se reflejará en el APK
echo       instalado con solo reiniciar la aplicación.
echo.
echo Presiona CTRL+C para detener los servicios.
pause