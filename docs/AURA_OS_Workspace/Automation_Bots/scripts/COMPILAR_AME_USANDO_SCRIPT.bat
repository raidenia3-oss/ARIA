@echo off
title Compilación de AME usando Script Existente
color 0A

echo =============================================
echo COMPILACION DE AME USANDO SCRIPT EXISTENTE
echo =============================================

echo.
echo 1/2 - Ejecutando build de producción...
cd dist
call npm run build

if %ERRORLEVEL% neq 0 (
    echo Error al compilar el proyecto.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo 2/2 - Compilando APK usando build_apk.bat...
call build_apk.bat

if %ERRORLEVEL% neq 0 (
    echo Error al compilar el APK.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo =============================================
echo Verificando ubicación del APK generado...
echo =============================================

if exist dist\app-debug.apk (
    echo APK encontrado en la raíz del proyecto.
    echo Copiando APK al escritorio como AME_PROD.apk...
    copy "dist\app-debug.apk" "%USERPROFILE%\Desktop\AME_PROD.apk"
    echo APK copiado a: %USERPROFILE%\Desktop\AME_PROD.apk
) else (
    echo No se encontró el APK en la ruta esperada.
    echo Buscando APKs generados en la carpeta android...
    cd android
    if exist app\build\outputs\apk\debug\app-debug.apk (
        echo APK encontrado en android/app/build/outputs/apk/debug/app-debug.apk
        echo Copiando APK al escritorio como AME_PROD.apk...
        copy "app\build\outputs\apk\debug\app-debug.apk" "%USERPROFILE%\Desktop\AME_PROD.apk"
        echo APK copiado a: %USERPROFILE%\Desktop\AME_PROD.apk
    ) else (
        echo No se encontró el APK en la ruta esperada dentro de android.
        pause
        exit /b 1
    )
)

echo.
echo =============================================
echo Proceso completado con éxito.
echo APK disponible en: %USERPROFILE%\Desktop\AME_PROD.apk
echo =============================================

pause