@echo off
echo =============================================
echo COMPILACION MANUAL DEL APK DE AME
echo =============================================

echo.
echo PASO 1: Copiando archivos necesarios a la carpeta android...
xcopy /Y /E ..\AME_Core\static\js ..\dist\android\app\src\main\assets\public\static\js
xcopy /Y /E ..\AME_Core\static\css ..\dist\android\app\src\main\assets\public\static\css
xcopy /Y ..\AME_Core\dashboard.html ..\dist\android\app\src\main\assets\public

echo.
echo PASO 1 completado con éxito.

echo.
echo PASO 2: Compilando el APK usando Gradle...
cd ..\dist\android
echo Ejecutando gradlew assembleDebug...
call gradlew assembleDebug

if %ERRORLEVEL% neq 0 (
    echo Error al compilar el APK.
    exit /b 1
)

echo.
echo PASO 2 completado con éxito.

echo.
echo PASO 3: Copiando el APK al escritorio...
copy ..\dist\android\app\build\outputs\apk\debug\app-debug.apk "%USERPROFILE%\Desktop\AME_PROD.apk"

if %ERRORLEVEL% neq 0 (
    echo Error al copiar el APK al escritorio.
    exit /b 1
)

echo.
echo =============================================
echo APK compilado y copiado al escritorio como AME_PROD.apk
echo =============================================