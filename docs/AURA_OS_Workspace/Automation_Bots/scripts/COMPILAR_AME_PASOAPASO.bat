@echo off
title Compilación Paso a Paso de AME - Producción
color 0A

echo =============================================
echo COMPILACION PASO A PASO DE AME - PRODUCCION
echo =============================================

echo.
echo PASO 1/4: Sincronizando Capacitor con Android...
call npx cap sync android

if %ERRORLEVEL% neq 0 (
    echo Error en PASO 1: Sincronización de Capacitor fallida.
    echo Por favor, verifica que Capacitor esté instalado correctamente.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo PASO 1 completado con éxito.

echo.
echo PASO 2/4: Ejecutando build de producción en el frontend...
cd dist
call npm run build

if %ERRORLEVEL% neq 0 (
    echo Error en PASO 2: Build de producción fallido.
    echo Por favor, verifica que npm esté instalado y las dependencias sean correctas.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo PASO 2 completado con éxito.

echo.
echo PASO 3/4: Compilando APK manualmente...
cd ..
echo.
echo Abre una nueva terminal y ejecuta manualmente:
echo cd dist\android
echo .\gradlew.bat assembleDebug

echo.
echo Una vez completado el proceso de compilación, continua con el siguiente paso.

pause

echo.
echo PASO 4/4: Copiando APK al escritorio...
echo.
echo Verifica que el APK haya sido generado en:
echo dist\android\app\build\outputs\apk\debug\app-debug.apk

if exist dist\android\app\build\outputs\apk\debug\app-debug.apk (
    echo Copiando APK al escritorio como AME_PROD.apk...
    copy "dist\android\app\build\outputs\apk\debug\app-debug.apk" "%USERPROFILE%\Desktop\AME_PROD.apk"
    echo APK copiado a: %USERPROFILE%\Desktop\AME_PROD.apk
) else (
    echo No se encontró el APK en la ruta esperada.
    echo Por favor, verifica que el APK haya sido generado correctamente.
    pause
    exit /b 1
)

echo.
echo =============================================
echo Compilación completada con éxito.
echo APK disponible en: %USERPROFILE%\Desktop\AME_PROD.apk
echo =============================================

pause