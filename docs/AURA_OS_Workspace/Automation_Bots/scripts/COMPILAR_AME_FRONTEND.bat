@echo off
title Compilación del Frontend de AME - Producción
color 0A

echo =============================================
echo COMPILACION DEL FRONTEND DE AME - PRODUCCION
echo =============================================

echo.
echo PASO 1/1: Sincronizando Capacitor con Android (sin build de Android)...
call npx cap sync android --no-android

if %ERRORLEVEL% neq 0 (
    echo Error en PASO 1: Sincronización de Capacitor fallida.
    echo Por favor, verifica que Capacitor esté instalado correctamente.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo PASO 1 completado con éxito.

echo.
echo PASO 2/2: Ejecutando build de producción del frontend...
cd dist
call npm run build

if %ERRORLEVEL% neq 0 (
    echo Error en PASO 2: Build de producción fallido.
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
echo Ahora sigue estos pasos para compilar el APK manualmente:

echo 1. Copia los archivos generados en la carpeta "dist" a:
echo    dist\android\app\src\main\assets\public

echo 2. Abre una terminal en la carpeta "dist\android".
echo 3. Ejecuta el siguiente comando para compilar el APK:
echo    .\gradlew.bat assembleDebug

echo 4. Una vez generado el APK, verifica que esté en:
echo    dist\android\app\build\outputs\apk\debug\app-debug.apk

echo 5. Copia el APK al escritorio como AME_PROD.apk:
echo    copy "dist\android\app\build\outputs\apk\debug\app-debug.apk" "%USERPROFILE%\Desktop\AME_PROD.apk"

echo.
echo =============================================
echo Instrucciones completadas.
echo =============================================

pause