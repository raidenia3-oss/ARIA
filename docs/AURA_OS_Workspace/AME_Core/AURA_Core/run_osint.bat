@echo off
cd /d "C:\Users\User\Downloads\AURA\AURA_Core"
:: Ejecutar usando el python del entorno virtual
".\venv\Scripts\python.exe" osint_engine.py %*
exit