@echo off
cd /d C:\Users\User\Downloads\AURA\ARIA_APP/backend
:loop
C:\Users\User\Downloads\AURA\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001
echo [%date% %time%] Backend crashed, restarting in 5 seconds...
timeout /t 5 /nobreak > nul
goto loop