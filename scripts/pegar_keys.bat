@echo off
chcp 65001 >nul
title AURA — Pegar API Keys
echo.
echo ============================================
echo   PEGA TUS API KEYS ACA
echo ============================================
echo.
echo Abriendo .env.local en Notepad...
echo.
echo Pegá tus keys en los campos vacios:
echo   GROQ_API_KEY=gsk_...
echo   DEEPSEEK_API_KEY=sk-...
echo   etc.
echo.
pause
notepad "%~dp0..\ame_backend\.env.local"
echo.
echo Guardá el archivo en Notepad (Ctrl+S) y cerrá.
echo.
pause
