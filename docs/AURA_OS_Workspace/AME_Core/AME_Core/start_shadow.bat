@echo off
cd /d C:\Users\User\Downloads\AURA\AME_Core
start /B python shadow_core.py
echo Shadow-Core iniciado en background
timeout /t 3 >nul
python -c "import sys; sys.path.insert(0,'.'); import socket; s=socket.socket(); s.settimeout(2); r=s.connect_ex(('127.0.0.1',5001)); print('Puerto 5001:', 'LISTENING' if r==0 else 'OFFLINE'); s.close()"
pause