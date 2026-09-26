@echo off
:: AURA Desktop — Standalone App Launcher
:: No browser, no localhost, no external dependencies required for chat
:: Just run this and everything is inside the app

title AURA Desktop

:: Hide console window and launch app
start "" /B pythonw.exe aura_app.py
