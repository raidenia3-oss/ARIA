@echo off
title Compilación Simple de AME - Producción
color 0A

echo =============================================
echo COMPILACION SIMPLE DE AME - PRODUCCION
echo =============================================

echo.
echo 1/3 - Entrando al directorio del frontend y ejecutando build...
cd dist
call npm run build

if %ERRORLEVEL% neq 0 (
    echo Error al compilar el proyecto.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo 2/3 - Sincronizando Capacitor con Android...
call npx cap sync android

if %ERRORLEVEL% neq 0 (
    echo Error al sincronizar Capacitor.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo 3/3 - Compilando APK usando gradlew.bat...
cd android
call gradlew.bat assembleDebug --no-daemon --stacktrace

if %ERRORLEVEL% neq 0 (
    echo Error al compilar el APK.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo =============================================
echo Verificando ubicación del APK generado...
echo =============================================

if exist app\build\outputs\apk\debug\*.apk (
    echo APK encontrado.
    echo Copiando APK al escritorio como AME_PROD.apk...

    for %%F in (app\build\outputs\apk\debug\*.apk) do (
        copy "%%F" "%USERPROFILE%\Desktop\AME_PROD.apk"
        echo APK copiado a: %USERPROFILE%\Desktop\AME_PROD.apk
    )
) else (
    echo No se encontró ningún APK en la ruta esperada.
    echo Verificando otras ubicaciones posibles...
    dir /s /b app\build\outputs\apk\debug\*.apk > apk_paths.txt
    if exist apk_paths.txt (
        for /f "delims=" %%F in (apk_paths.txt) do (
            echo APK encontrado en: %%F
            copy "%%F" "%USERPROFILE%\Desktop\AME_PROD.apk"
            echo APK copiado a: %USERPROFILE%\Desktop\AME_PROD.apk
        )
        del apk_paths.txt
    ) else (
        echo No se encontraron APKs generados.
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