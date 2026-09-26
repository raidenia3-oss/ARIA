@echo off
title Compilación Final del Frontend de AME con Biometría
color 0A

echo =============================================
echo COMPILACION FINAL DEL FRONTEND DE AME
echo Con integración de autenticación biométrica
echo =============================================

echo.
echo PASO 0: Preparando entorno...
echo Copiando index.html a AME_Core para configurar Capacitor...
copy dist\index.html AME_Core\

if %ERRORLEVEL% neq 0 (
    echo Error al copiar index.html.
    exit /b 1
)

echo Configurando Capacitor para usar AME_Core como directorio web...
cd dist
call npx cap set web-dir ../AME_Core

if %ERRORLEVEL% neq 0 (
    echo Error al configurar el directorio web en Capacitor.
    exit /b 1
)

echo.
echo PASO 0 completado con éxito.

echo.
echo PASO 1: Copiando archivos del frontend desde AME_Core a dist...
echo Copiando archivos HTML desde AME_Core/templates a dist...
xcopy /Y /E AME_Core\templates\*.html dist\

if %ERRORLEVEL% neq 0 (
    echo Error al copiar archivos HTML.
    exit /b 1
)

echo Copiando archivos CSS desde AME_Core/static/css a dist...
xcopy /Y /E AME_Core\static\css\*.css dist\

if %ERRORLEVEL% neq 0 (
    echo Error al copiar archivos CSS.
    exit /b 1
)

echo Copiando archivos JS desde AME_Core/static/js a dist...
xcopy /Y /E AME_Core\static\js\*.js dist\

if %ERRORLEVEL% neq 0 (
    echo Error al copiar archivos JS.
    exit /b 1
)

echo Copiando dashboard.html desde AME_Core a dist...
xcopy /Y AME_Core\dashboard.html dist\

if %ERRORLEVEL% neq 0 (
    echo Error al copiar dashboard.html.
    exit /b 1
)

echo.
echo PASO 1 completado con éxito.

echo.
echo PASO 2: Instalando dependencias en la carpeta dist...
cd dist
call npm install

if %ERRORLEVEL% neq 0 (
    echo Error al instalar dependencias.
    exit /b 1
)

echo.
echo PASO 2 completado con éxito.

echo.
echo PASO 3: Sincronizando Capacitor con Android...
call npx cap sync android

if %ERRORLEVEL% neq 0 (
    echo Error al sincronizar Capacitor.
    exit /b 1
)

echo.
echo PASO 3 completado con éxito.

echo.
echo PASO 4: Compilando el APK con Gradle...
cd android
call gradlew.bat assembleDebug

if %ERRORLEVEL% neq 0 (
    echo Error al compilar con Gradle.
    exit /b 1
)

echo.
echo =============================================
echo APK compilado con éxito en android/app/build/outputs/apk/debug/
echo =============================================

echo.
echo El APK generado se encuentra en:
echo android/app/build/outputs/apk/debug/app-debug.apk

echo.
echo Copiando el APK al escritorio como AME_PROD.apk...
copy android\app\build\outputs\apk\debug\app-debug.apk "%USERPROFILE%\Desktop\AME_PROD.apk"

if %ERRORLEVEL% neq 0 (
    echo Error al copiar el APK al escritorio.
    exit /b 1
)

echo.
echo =============================================
echo APK copiado al escritorio como AME_PROD.apk
echo =============================================

echo.
echo Integración de autenticación biométrica completada.
echo El APK ahora incluye soporte para autenticación biométrica.
echo =============================================