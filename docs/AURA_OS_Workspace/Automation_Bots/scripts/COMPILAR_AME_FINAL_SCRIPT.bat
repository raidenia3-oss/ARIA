@echo off
title Compilación Final del Frontend de AME
color 0A

echo =============================================
echo COMPILACION FINAL DEL FRONTEND DE AME
echo =============================================

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

exit /b 0