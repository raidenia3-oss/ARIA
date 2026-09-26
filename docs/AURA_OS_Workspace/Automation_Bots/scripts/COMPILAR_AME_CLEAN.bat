@echo off
title Compilación Limpia de AME - Producción
color 0A

echo =============================================
echo COMPILACION LIMPIA DE AME - PRODUCCION
echo =============================================

echo.
echo 1/5 - Limpiando archivos temporales de Gradle...
cd dist\android
if exist gradle rmdir /s /q gradle
if exist .gradle rmdir /s /q .gradle
if exist gradlew.bat del gradlew.bat
if exist gradlew del gradlew

echo.
echo 2/5 - Sincronizando Capacitor con Android...
cd ..\..
call npx cap sync android

if %ERRORLEVEL% neq 0 (
    echo Error al sincronizar Capacitor.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo 3/5 - Ejecutando build de producción...
cd dist
call npm run build

if %ERRORLEVEL% neq 0 (
    echo Error al compilar el proyecto.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo 4/5 - Compilando APK usando gradlew.bat...
cd android
call gradlew.bat assembleDebug --no-daemon --stacktrace

if %ERRORLEVEL% neq 0 (
    echo Error al compilar el APK.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo 5/5 - Verificando ubicación del APK generado...
cd ..\..
if exist dist\app-debug.apk (
    echo APK encontrado en la raíz del proyecto.
    echo Copiando APK al escritorio como AME_PROD.apk...
    copy "dist\app-debug.apk" "%USERPROFILE%\Desktop\AME_PROD.apk"
    echo APK copiado a: %USERPROFILE%\Desktop\AME_PROD.apk
) else (
    echo No se encontró el APK en la ruta esperada.
    echo Buscando APKs generados...
    dir /s /b dist\*.apk > apk_paths.txt
    if exist apk_paths.txt (
        echo Encontrados APKs alternativos:
        for /f "delims=" %%F in (apk_paths.txt) do (
            echo Copiando %%F al escritorio...
            copy "%%F" "%USERPROFILE%\Desktop\AME_PROD.apk"
        )
        del apk_paths.txt
        echo APK copiado a: %USERPROFILE%\Desktop\AME_PROD.apk
    ) else (
        echo No se encontraron APKs generados.
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