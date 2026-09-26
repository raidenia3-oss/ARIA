@echo off
title Compilación Final de AME - Producción
color 0A

echo =============================================
echo COMPILACION FINAL DE AME - PRODUCCION
echo =============================================

echo.
echo 1/5 - Creando estructura de assets para Capacitor...
cd dist
if not exist android\app\src\main\assets\public (
    mkdir android\app\src\main\assets\public
)
if not exist android\app\src\main\assets\public\js (
    mkdir android\app\src\main\assets\public\js
)
if not exist android\app\src\main\assets\public\css (
    mkdir android\app\src\main\assets\public\css
)

echo.
echo 2/5 - Copiando archivos del frontend a assets...
copy ..\AME_Core\index.html android\app\src\main\assets\public\
xcopy ..\AME_Core\static\js\*.js android\app\src\main\assets\public\js /E /Y /I
xcopy ..\AME_Core\static\css\*.css android\app\src\main\assets\public\css /E /Y /I

echo.
echo 3/5 - Sincronizando proyecto con Capacitor...
call npx cap sync android

if %ERRORLEVEL% neq 0 (
    echo Error al sincronizar el proyecto con Capacitor.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo 4/5 - Compilando APK usando build_apk.bat...
cd dist
call build_apk.bat

if %ERRORLEVEL% neq 0 (
    echo Error al compilar el APK.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo 5/5 - Buscando APK generado...
if exist android\app\build\outputs\apk\debug\app-debug.apk (
    copy "android\app\build\outputs\apk\debug\app-debug.apk" "..\AME_PROD.apk"
    echo APK copiado a la raíz del proyecto como AME_PROD.apk.
) else (
    echo No se encontró el APK en la ruta esperada: android\app\build\outputs\apk\debug\app-debug.apk
    pause
    exit /b 1
)

echo.
echo 6/5 - Actualizando version.json...
cd ..\
setlocal enabledelayedexpansion
set "version_file=version.json"
set "new_version=1.0.2"
(
    echo {
    echo   "version": "!new_version!",
    echo   "build": 2,
    echo   "release_date": "%date%",
    echo   "description": "Compilación final con nodos tácticos integrados"
    echo }
) > "!version_file!"

echo Version.json actualizado con versión !new_version!

echo.
echo =============================================
echo Proceso completado con éxito.
echo APK disponible en: %CD%\AME_PROD.apk
echo =============================================

pause