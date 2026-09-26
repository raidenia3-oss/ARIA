@echo off
title Compilación del Frontend de AME - Copiar y Compilar
color 0A

echo =============================================
echo COMPILACION DEL FRONTEND DE AME - COPIAR Y COMPILAR
echo =============================================

echo.
echo PASO 1/3: Copiando archivos del frontend desde AME_Core a dist...
echo Copiando archivos HTML desde AME_Core/templates a dist...
xcopy /Y AME_Core\templates\*.html dist\

if %ERRORLEVEL% neq 0 (
    echo Error al copiar archivos HTML.
    pause
    exit /b %ERRORLEVEL%
)

echo Copiando archivos CSS desde AME_Core/static/css a dist...
xcopy /Y AME_Core\static\css\*.css dist\

if %ERRORLEVEL% neq 0 (
    echo Error al copiar archivos CSS.
    pause
    exit /b %ERRORLEVEL%
)

echo Copiando archivos JS desde AME_Core/static/js a dist...
xcopy /Y AME_Core\static\js\*.js dist\

if %ERRORLEVEL% neq  otros archivos de AME_Core a dist...
xcopy /Y AME_Core\dashboard.html dist\

if %ERRORLEVEL% neq 0 (
    echo Error al copiar dashboard.html.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo PASO 1 completado con éxito.

echo.
echo PASO 2/3: Instalando dependencias en la carpeta dist...
cd dist
call npm install

if %ERRORLEVEL% neq 0 (
    echo Error al instalar dependencias.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo PASO 2 completado con éxito.

echo.
echo PASO 3/3: Compilando el frontend...
call npm run build

if %ERRORLEVEL% neq 0 (
    echo Error al compilar el proyecto.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo =============================================
echo Frontend compilado con éxito en la carpeta dist.
echo =============================================

echo.
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