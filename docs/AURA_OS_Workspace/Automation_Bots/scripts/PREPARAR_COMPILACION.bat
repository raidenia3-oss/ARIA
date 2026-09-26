@echo off
title Preparación para Compilación de AME
color 0A

echo =============================================
echo PREPARACION PARA COMPILACION DE AME
echo =============================================

echo.
echo 1/2 - Sincronizando Capacitor con Android...
call npx cap sync android

if %ERRORLEVEL% neq 0 (
    echo Error al sincronizar Capacitor.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo =============================================
echo Preparación completada con éxito.
echo =============================================

echo.
echo Ahora sigue estos pasos para compilar el APK:

echo 1. Abre una terminal en la carpeta "dist".
echo 2. Ejecuta el siguiente comando para compilar el proyecto:
echo    npm run build

echo 3. Una vez completado el build, abre otra terminal en la carpeta "dist\android".
echo 4. Ejecuta el siguiente comando para compilar el APK:
echo    .\gradlew.bat assembleDebug

echo 5. El APK generado se encontrará en:
echo    dist\android\app\build\outputs\apk\debug\app-debug.apk

echo 6. Copia el APK al escritorio como AME_PROD.apk:
echo    copy "dist\android\app\build\outputs\apk\debug\app-debug.apk" "%USERPROFILE%\Desktop\AME_PROD.apk"

echo =============================================
echo Instrucciones completadas.
echo =============================================

pause