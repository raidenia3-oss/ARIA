@echo off
cd /d "%~dp0"
call venv_decision_core\Scripts\activate.bat
pip install flask-socketio