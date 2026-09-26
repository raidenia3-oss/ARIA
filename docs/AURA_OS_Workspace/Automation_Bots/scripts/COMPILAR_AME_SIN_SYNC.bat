@echo off
title Compilación del Frontend de AME - Producción (Sin Sync)
color 0A

echo =============================================
echo COMPILACION DEL FRONTEND DE AME - PRODUCCION
echo (Sin sincronización con Android)
echo =============================================

echo.
echo PASO 1/1: Ejecutando build de producción del frontend...
cd dist
call npm run build

if %ERRORLEVEL% neq 0 (
    echo Error en PASO 1: Build de producción fallido.
    echo Por favor, verifica que npm esté instalado y las dependencias sean correctas.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo =============================================
echo Build del frontend completado con éxito.
echo =============================================

echo.
echo Los archivos de producción están listos en la carpeta "dist".
echo Ahora sigue estos pasos para preparar el entorno y compilar el APK:

echo 1. Copia manualmente los archivos generados en la carpeta "dist" a:
echo    dist\android\app\src\main\assets\public

echo 2. Ejecuta el siguiente comando para sincronizar Capacitor con Android:
echo    npx cap sync android

echo 3. Abre una terminal en la carpeta "dist\android".
echo 4. Ejecuta el siguiente comando para compilar el APK:
echo    .\gradlew.bat assembleDebug

echo 5. Una vez generado el APK, verifica que esté en:
echo    dist\android\app\build\outputs\apk\debug\app-debug.apk

echo 6. Copia el APK al escritorio como AME_PROD.apk:
echo    copy "dist\android\app\build\outputs\apk\debug\app-debug.apk" "%USERPROFILE%\Desktop\AME_PROD.apk"

echo.
echo =============================================
echo Instrucciones completadas.
echo =============================================

pause