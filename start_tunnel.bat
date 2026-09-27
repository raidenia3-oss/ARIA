@echo off
:loop
"C:\Program Files\nodejs\node.exe" --no-warnings "C:\Users\User\AppData\Roaming\npm\node_modules\localtunnel\bin\lt.js" --port 8001 --subdomain aria-backend
echo [%date% %time%] Tunnel disconnected, reconnecting in 10 seconds...
timeout /t 10 /nobreak > nul
goto loop