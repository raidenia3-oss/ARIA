@echo off
title Compilación de Producción AME
color 0A

echo =============================================
echo INICIANDO COMPILACION DE PRODUCCION AME
echo =============================================

:: Cambiar al directorio del proyecto
cd /d "%~dp0"

:: Compilar el frontend web
echo Compilando el frontend web...
cd dist
call npm run build
if %ERRORLEVEL% neq 0 (
    echo Error al compilar el frontend web.
    pause
    exit /b %ERRORLEVEL%
)
cd ..

:: Sincronizar con Capacitor para Android
echo Sincronizando con Capacitor para Android...
cd dist
call npx cap sync android
if %ERRORLEVEL% neq 0 (
    echo Error al sincronizar con Capacitor.
    pause
    exit /b %ERRORLEVEL%
)
cd ..

:: Compilar APK de producción
echo Compilando APK de producción...
cd dist/android
call gradlew assembleRelease
if %ERRORLEVEL% neq 0 (
    echo Error al compilar el APK de producción.
    pause
    exit /b %ERRORLEVEL%
)

:: Copiar el APK generado a la raíz del proyecto
echo Copiando APK a la raíz del proyecto...
if exist "app-release-unsigned.apk" (
    copy "app\build\outputs\apk\release\app-release-unsigned.apk" "%~dp0AME_PROD_FINAL.apk"
    if %ERRORLEVEL% equ 0 (
        echo APK copiado exitosamente como AME_PROD_FINAL.apk
    ) else (
        echo Error al copiar el APK.
        pause
        exit /b %ERRORLEVEL%
    )
) else (
    echo No se encontró el archivo app-release-unsigned.apk.
    pause
    exit /b 1
)

echo =============================================
echo COMPILACION DE PRODUCCION COMPLETADA CON EXITO
echo =============================================
echo El APK de producción se encuentra en:
echo %~dp0AME_PROD_FINAL.apk
pause