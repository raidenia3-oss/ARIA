@echo off
REM Script para corregir los permisos de la clave SSH en Windows
echo Corrigiendo permisos de la clave SSH...

REM Usar icacls para establecer permisos correctos
icacls "C:\Users\User\.ssh\id_rsa" /inheritance:r
icacls "C:\Users\User\.ssh\id_rsa" /grant:r "%USERNAME%:(R)"

echo Permisos corregidos.
echo.
echo Verificando permisos:
icacls "C:\Users\User\.ssh\id_rsa"
pause