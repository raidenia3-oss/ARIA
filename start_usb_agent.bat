@echo off
cd /d C:\Users\User\Downloads\AURA\usb-aria
:loop
"C:\Users\User\Downloads\AURA\.venv\Scripts\python.exe" aria_usb_agent.py
echo [%date% %time%] USB Agent stopped, restarting in 30 seconds...
timeout /t 30 /nobreak > nul
goto loop