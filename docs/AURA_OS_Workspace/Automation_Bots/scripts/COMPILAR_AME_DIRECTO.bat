@echo off
title Compilación Directa de AME - Producción
color 0A

echo =============================================
echo COMPILACION DIRECTA DE AME - PRODUCCION
echo =============================================

echo.
echo 1/3 - Sincronizando Capacitor con Android...
call npx cap sync android

if %ERRORLEVEL% neq 0 (
    echo Error al sincronizar Capacitor.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo 2/3 - Ejecutando build de producción sin Android...
cd dist
call npm run build -- --no-android

if %ERRORLEVEL% neq 0 (
    echo Error al compilar el proyecto.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo 3/3 - Copiando archivos de build a Android...
cd ..
xcopy /E /Y dist\* dist\android\app\src\main\assets\public\

echo.
echo =============================================
echo Archivos copiados. Ahora compile manualmente el APK:
echo 1. Abre una terminal en la carpeta dist\android
echo 2. Ejecuta: .\gradlew.bat assembleDebug
echo =============================================

echo.
echo Verificando ubicación del APK generado...
echo =============================================

cd android
if exist app\build\outputs\apk\debug\app-debug.apk (
    echo APK encontrado en android/app/build/outputs/apk/debug/app-debug.apk
    echo Copiando APK al escritorio como AME_PROD.apk...
    copy "app\build\outputs\apk\debug\app-debug.apk" "%USERPROFILE%\Desktop\AME_PROD.apk"
    echo APK copiado a: %USERPROFILE%\Desktop\AME_PROD.apk
) else (
    echo No se encontró el APK en la ruta esperada.
    echo Buscando todos los APKs generados...
    dir /s /b app\build\outputs\apk\debug\*.apk > apk_paths.txt
    if exist apk_paths.txt (
        echo Encontrados APKs:
        for /f "delims=" %%F in (apk_paths.txt) do (
            echo Copiando %%F al escritorio...
            copy "%%F" "%USERPROFILE%\Desktop\AME_PROD.apk"
        )
        del apk_paths.txt
        echo APK copiado a: %USERPROFILE%\Desktop\AME_PROD.apk
    ) else (
        echo No se encontraron APKs generados.
        echo Por favor, compile manualmente el APK usando el comando:
        echo .\gradlew.bat assembleDebug
        pause
        exit /b 1
    )
)

echo.
echo =============================================
echo Proceso completado.
echo APK disponible en: %USERPROFILE%\Desktop\AME_PROD.apk
echo =============================================

pause