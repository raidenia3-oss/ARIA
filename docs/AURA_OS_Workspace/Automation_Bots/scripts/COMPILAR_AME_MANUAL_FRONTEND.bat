@echo off
title Compilación Manual del Frontend de AME
color 0A

echo =============================================
echo COMPILACION MANUAL DEL FRONTEND DE AME
echo =============================================

echo.
echo PASO 1/2: Copiando archivos del frontend a la carpeta dist...
echo Copiando archivos desde la carpeta raíz a dist...
xcopy /E /Y src\* dist\

if %ERRORLEVEL% neq 0 (
    echo Error al copiar archivos del frontend.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo PASO 1 completado con éxito.

echo.
echo PASO 2/2: Compilando el frontend directamente con npm...
cd dist
call npm install
if %ERRORLEVEL% neq 0 (
    echo Error al instalar dependencias.
    pause
    exit /b %ERRORLEVEL%
)

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