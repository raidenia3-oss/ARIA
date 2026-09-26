@echo off
start "" "C:\Users\User\AppData\Local\Programs\Ollama\ollama.exe" serve
timeout /t 15 /nobreak >nul
start "" /min "C:\Users\User\Documents\Proyectos\ngrok.exe" http --domain=scabbed-uneven-habitant.ngrok-free.dev 11434
start "" /min wsl -d Ubuntu -e bash -c "export PATH='/home/raiden/.local/bin:$PATH' && hermes gateway"