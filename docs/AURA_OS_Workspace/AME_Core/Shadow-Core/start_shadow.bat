@echo off
:: Shadow-Core Startup Script
:: Inicia Ollama Proxy, Action Executor, Gesture Processor y luego Shadow-Core

start "Ollama Proxy" cmd /c python Shadow-Core\ollama_proxy.py
timeout /t 3 >nul
start "Action Executor" cmd /c python Shadow-Core\action_executor.py
timeout /t 3 >nul
start "Gesture Processor" cmd /c python Shadow-Core\gesture_processor.py
timeout /t 3 >nul
python start_watchdog.py
