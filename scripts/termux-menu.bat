@echo off
chcp 65001 >nul
title AURA - Termux Connect Menu
cd /d C:\Users\User\Downloads\AURA\scripts
powershell -NoProfile -ExecutionPolicy Bypass -File "termux-connect.ps1" -Menu
pause
