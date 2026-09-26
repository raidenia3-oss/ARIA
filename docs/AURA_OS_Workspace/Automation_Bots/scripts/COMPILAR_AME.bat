@echo off
:: Archivo de lote para compilar AME con actualización automática de versión
:: Este script incrementa el número de build en version.json y compila el APK

echo =============================================
echo 🚀 COMPILANDO AME CON ACTUALIZACIÓN AUTOMÁTICA
echo =============================================

:: Verificar si el entorno está configurado correctamente
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ❌ Error: Python no está disponible en el PATH.
    echo 🔧 Por favor, asegúrate de que Python esté instalado y en el PATH.
    pause
    exit /b 1
)

where npm >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ❌ Error: npm no está disponible en el PATH.
    echo 🔧 Por favor, asegúrate de que Node.js esté instalado y en el PATH.
    pause
    exit /b 1
)

:: Verificar que estemos en el directorio correcto
cd /d "%~dp0" || (
    echo ❌ Error: No se puede cambiar al directorio del proyecto.
    echo 🔧 Por favor, ejecuta este script desde la raíz del proyecto AURA.
    pause
    exit /b 1
)

:: 1. Incrementar el número de build en version.json
echo 📝 Actualizando versión en version.json...
if exist "version.json" (
    :: Leer el archivo version.json
    for /f "delims={} tokens=2,*" %%A in ('findstr /n "^" version.json ^| findstr /b ":{"') do (
        set line=%%B
    )

    :: Extraer la línea con "build"
    for /f "tokens=2 delims=: " %%A in ("%line%") do (
        set build_line=%%A
    )

    :: Buscar el número de build
    for /f "tokens=2 delims=: " %%A in ("%build_line%") do (
        set build=%%A
    )

    :: Incrementar el número de build
    set /a build+=1

    :: Reemplazar el número de build en el archivo
    setlocal enabledelayedexpansion
    set "file=version.json"
    set "tempFile=version.json.tmp"

    (for /f "delims=" %%i in ('type "version.json"') do (
        set "line=%%i"
        echo !line!
        if "!line!"=="    ""build"": !build!," (
            echo    ""build"": !build!,
        )
    )) > "!tempFile!"

    move /y "!tempFile!" "version.json" >nul
    echo ✅ Versión actualizada a build !build!
) else (
    echo ❌ Error: No se encontró el archivo version.json.
    echo 🔧 Por favor, asegúrate de que el archivo version.json exista en la raíz del proyecto.
    pause
    exit /b 1
)

:: 2. Compilar el frontend web
echo 🖥️ Compilando frontend web...
call npm run build || (
    echo ❌ Error al compilar el frontend.
    pause
    exit /b 1
)

:: 3. Sincronizar con Capacitor para Android
echo 🔗 Sincronizando con Capacitor para Android...
call npx cap sync android || (
    echo ❌ Error al sincronizar con Capacitor.
    pause
    exit /b 1
)

:: 4. Compilar el APK usando Gradle
echo 📱 Compilando APK con Gradle...
cd android || (
    echo ❌ Error: No se puede cambiar al directorio android.
    pause
    exit /b 1
)

:: Verificar que Android SDK esté disponible
where gradlew >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ❌ Error: gradlew no está disponible. Android SDK no está configurado correctamente.
    echo 🔧 Por favor, asegúrate de que el Android SDK esté instalado y configurado.
    pause
    exit /b 1
)

:: Compilar el APK en modo release
call gradlew assembleRelease || (
    echo ❌ Error al compilar el APK.
    pause
    exit /b 1
)

:: 5. Copiar el APK a la carpeta de distribución
echo 📂 Copiando APK a la carpeta de distribución...
cd .. || (
    echo ❌ Error: No se puede cambiar al directorio raíz.
    pause
    exit /b 1
)

if exist "dist\AME_Client_v1.apk" (
    echo ⚠️  Advertencia: APK existente encontrado. Sobrescribiendo...
    del "dist\AME_Client_v1.apk" >nul 2>&1
)

copy "android\app\build\outputs\apk\release\app-release.apk" "dist\AME_Client_v1.apk" || (
    echo ❌ Error al copiar el APK a la carpeta de distribución.
    pause
    exit /b 1
)

:: 6. Mostrar información de la versión actualizada
echo =============================================
echo 🎉 COMPILACIÓN COMPLETADA CON ÉXITO
echo =============================================

:: Mostrar la versión actualizada
for /f "tokens=2 delims=: " %%A in ('findstr /c "version" version.json') do (
    set version=%%A
)
for /f "tokens=2 delims=: " %%A in ('findstr /c "build" version.json') do (
    set build=%%A
)

echo Versión actualizada: %version%
echo Número de build: %build%
echo APK generado: dist\AME_Client_v1.apk

:: Verificar que el APK exista
if exist "dist\AME_Client_v1.apk" (
    echo ✅ APK listo para distribución en: dist\AME_Client_v1.apk
) else (
    echo ❌ Error: No se pudo generar el APK.
    pause
    exit /b 1
)

echo =============================================
echo 🔄 El sistema OTA ahora detectará esta versión
echo    como la última disponible para actualización.
echo =============================================

pause