@echo off
chcp 65001 >nul
title AURA - Termux Remote-SSH
echo.
echo Abriendo VS Code Remote-SSH hacia Termux...
echo Host: termux (192.168.18.21:8022)
echo.
code --remote ssh-remote+termux /data/data/com.termux/files/home
pause
