@echo off
cd /d C:\Users\User\Downloads\AURA
:loop
C:\Users\User\Downloads\AURA\.venv\Scripts\python.exe aria_autonomous.py
echo [%date% %time%] Autonomous agent stopped, restarting in 30 seconds...
timeout /t 30 /nobreak > nul
goto loop