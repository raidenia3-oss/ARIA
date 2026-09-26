@echo off
title AURA - Lanzador Automatico
color 0A

echo ========================================
echo        AURA SYSTEM - LAUNCHER
echo ========================================
echo.
echo [1/3] Iniciando Shadow-Core (Puerto 5001)...
start /MIN cmd /c "cd /d C:\Users\User\Downloads\AURA\AME_Core && python shadow_core.py"
echo       Shadow-Core lanzado en background.
echo.

echo [2/3] Esperando 3 segundos para inicializar...
timeout /t 3 /nobreak >nul
echo       Listo.
echo.

echo [3/3] Iniciando Main Core (Puerto 5000)...
start /MIN cmd /c "cd /d C:\Users\User\Downloads\AURA\AME_Core && python servidor_ame.py"
echo       Main Core lanzado en background.
echo.

echo Abriendo navegador en http://127.0.0.1:5000 ...
timeout /t 2 /nobreak >nul
start http://127.0.0.1:5000
echo.
echo ========================================
echo   AURA operativo - Revisa la ventana
echo ========================================
echo.
pause