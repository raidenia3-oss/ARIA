@echo off
title LazyIncome-Hub
cd /d "%~dp0\lazy_income_hub"
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Falta entorno virtual. Ejecuta: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)
.venv\Scripts\python.exe main.py
pause
