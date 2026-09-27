  
@echo off  
cd /d C:\\Users\\User\\Downloads\\AURA\\ARIA_APP\\backend  
python -m uvicorn app:app --host 127.0.0.1 --port 8001  
:loop  
python -m uvicorn app:app --host 127.0.0.1 --port 8001  
goto loop 
