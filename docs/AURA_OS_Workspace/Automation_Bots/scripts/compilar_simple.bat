@echo off
echo =============================================
echo COMPILACION SIMPLIFICADA DEL APK DE AME
echo =============================================

echo.
echo PASO 1: Copiando archivos JS y CSS a la carpeta android...
mkdir ..\dist\android\app\src\main\assets\public\static\js 2>nul
mkdir ..\dist\android\app\src\main\assets\public\static\css 2>nul

xcopy ..\AME_Core\static\js\*.js ..\dist\android\app\src\main\assets\public\static\js /Y /E /I
xcopy ..\AME_Core\static\css\*.css ..\dist\android\app\src\main\assets\public\static\css /Y /E /I
copy ..\AME_Core\dashboard.html ..\dist\android\app\src\main\assets\public\ /Y

echo.
echo PASO 1 completado con éxito.

echo.
echo PASO 2: Compilando el APK...
cd ..\dist\android
echo Ejecutando compilación con Gradle...
call gradlew.bat assembleDebug

if %ERRORLEVEL% neq 0 (
    echo Error al compilar el APK.
    exit /b 1
)

echo.
echo PASO 2 completado con éxito.

echo.
echo PASO 3: Copiando el APK al escritorio...
copy ..\dist\android\app\build\outputs\apk\debug\app-debug.apk "%USERPROFILE%\Desktop\AME_PROD.apk" /Y

if %ERRORLEVEL% neq 0 (
    echo Error al copiar el APK al escritorio.
    exit /b 1
)

echo.
echo =============================================
echo APK compilado y copiado al escritorio como AME_PROD.apk
echo =============================================