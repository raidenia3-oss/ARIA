@echo off
:: AURA Run as Admin - Ejecuta un script con permisos de administrador
:: Este script abre una nueva ventana de cmd con permisos elevados

:: Verificar si el script de configuración existe
if not exist "%~dp0setup_task_with_admin.py" (
    echo Error: El script setup_task_with_admin.py no existe en %~dp0
    pause
    exit /b 1
)

:: Verificar si estamos ejecutando como administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Este script necesita permisos de administrador.
    echo Intentando elevar privilegios...

    :: Crear un acceso directo temporal para ejecutar como administrador
    setlocal
    set "vbsfile=%temp%\getadmin.vbs"
    set "cmdline=%~s0 %*"

    echo Set UAC = CreateObject^("Shell.Application"^) > "%vbsfile%"
    echo UAC.ShellExecute "cmd.exe", "/c %cmdline%", "", "runas", 1 >> "%vbsfile%"

    "%vbsfile%"
    del "%vbsfile%"
    exit /b 0
)

:: Ejecutar el script con permisos de administrador
echo Ejecutando setup_task_with_admin.py con permisos de administrador...
python "%~dp0setup_task_with_admin.py"

echo.
echo Configuración completada.
pause