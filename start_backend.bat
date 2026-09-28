@echo off
cd /d C:\Users\User\Downloads\AURA\ARIA_APP/backend
:loop
powershell -Command "Start-Process -WindowStyle Hidden -FilePath 'C:\Users\User\Downloads\AURA\.venv\Scripts\python.exe' -ArgumentList '-m uvicorn app:app --host 127.0.0.1 --port 8001' -WorkingDirectory 'C:\Users\User\Downloads\AURA\ARIA_APP/backend'"
REM Wait for backend to start
timeout /t 10 /nobreak > nul
REM Check if backend is running, if not loop
python -c "import requests; exit(0 if requests.get('http://127.0.0.1:8001/health', timeout=5).status_code == 200 else 1)" 2>nul
if errorlevel 1 (
    echo [%date% %time%] Backend health check failed, restarting...
) else (
    echo [%date% %time%] Backend running on port 8001
    timeout /t 60 /nobreak > nul
)
goto loop