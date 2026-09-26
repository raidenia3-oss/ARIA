@echo off
:: Script para iniciar Shadow-Core como servicio
start "Shadow-Core" cmd /c python Shadow-Core\start_shadow.bat
echo Shadow-Core iniciado.
