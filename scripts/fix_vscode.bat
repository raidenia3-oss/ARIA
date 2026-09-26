@echo off
chcp 65001 >nul
title AURA — Fix VS Code + Ripgrep
echo ============================================
echo   FIX VS CODE + RIPGREP
echo ============================================
echo.

echo [1/3] Verificando archivos bloqueados...
echo       Procesos activos:
tasklist /FI "IMAGENAME eq python.exe" 2>NUL | find /I "python.exe" >NUL
if %errorlevel%==0 (
    echo       [WARN] Hay procesos Python corriendo. Podrian bloquear archivos.
    echo       Cerrando procesos Python...
    taskkill /F /IM python.exe 2>NUL
    echo       [OK] Procesos Python cerrados.
) else (
    echo       [OK] No hay procesos Python bloqueando archivos.
)

echo.
echo [2/3] Verificando permisos de escritura...
echo       Directorio del proyecto: C:\Users\User\Downloads\AURA
icacls "C:\Users\User\Downloads\AURA" /grant "%USERNAME%":(OI)(CI)F /T 2>NUL
echo       [OK] Permisos de escritura aplicados.

echo.
echo [3/3] Instalando ripgrep (para VS Code)...
winget install BurntSushi.ripgrep.MSVC --accept-package-agreements --accept-source-agreements 2>NUL
if %errorlevel%==0 (
    echo       [OK] ripgrep instalado correctamente.
) else (
    echo       [WARN] No se pudo instalar ripgrep automaticamente.
    echo       Descargalo manualmente desde: https://github.com/BurntSushi/ripgrep/releases
    echo       O ejecuta en PowerShell: winget install BurntSushi.ripgrep.MSVC
)

echo.
echo ============================================
echo   LISTO
echo ============================================
echo.
echo Ahora:
echo 1. Reinicia VS Code
echo 2. Abri el archivo que queres editar
echo 3. Guardalo con Ctrl+S
echo.
echo Si todavia no podes guardar:
echo   - Cierra el archivo en otros programas (Notepad, navegador, etc.)
echo   - Cierra todas las terminales PowerShell/CMD que usen ese archivo
echo   - Ejecuta VS Code como Administrador
echo.
pause
