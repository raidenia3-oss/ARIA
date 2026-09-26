@echo off
REM AURA App Build Script - PyInstaller
REM Produces a standalone .exe

cd /d "C:\Users\User\Downloads\AURA"

if not exist ".venv\Scripts\python.exe" (
    echo Creando venv...
    python -m venv .venv
)

echo Instalando PyInstaller...
.venv\Scripts\python.exe -m pip install pyinstaller --quiet

echo Copiando ai_providers.py al directorio del app...
copy /Y ai_providers.py AURA_APP\backend\ai_providers.py >nul 2>&1

echo Limpiando cache de builds anteriores...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul
del /q "AURA OS.spec" 2>nul

echo Construyendo AURA App .exe...
.venv\Scripts\python.exe -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "AURA OS" ^
    --add-data "AURA_APP\frontend;frontend" ^
    --add-data "AURA_APP\backend\ai_providers.py;." ^
    --hidden-import ai_providers ^
    --hidden-import backend.skills.registry ^
    --hidden-import backend.skills.system.status ^
    --hidden-import backend.skills.system.time ^
    --hidden-import backend.skills.system.ping ^
    --hidden-import backend.skills.system.scan ^
    --hidden-import backend.skills.system.whois ^
    --hidden-import backend.skills.system.open ^
    --hidden-import backend.skills.system.volume ^
    --hidden-import backend.skills.system.lock ^
    --hidden-import backend.skills.system.apps ^
    --hidden-import backend.skills.system.screenshot ^
    --hidden-import backend.skills.system.memory ^
    --hidden-import backend.skills.web.search ^
    --hidden-import backend.skills.web.weather ^
    --hidden-import backend.skills.files.list ^
    --hidden-import backend.skills.files.read ^
    --hidden-import backend.skills.files.write ^
    --hidden-import backend.memory.working ^
    --hidden-import backend.memory.short_term ^
    --hidden-import backend.memory.long_term ^
    --hidden-import backend.voice.pipeline ^
    --hidden-import backend.vision.screen ^
    --hidden-import backend.proactive.engine ^
    --hidden-import backend.evolution.engine ^
    --hidden-import backend.learning.compound ^
    --hidden-import backend.api.compat ^
    --hidden-import edge_tts ^
    --hidden-import pyautogui ^
    --hidden-import psutil ^
    --collect-all fastapi ^
    --collect-all uvicorn ^
    --collect-all pydantic ^
    --collect-all edge_tts ^
    --collect-all pywebview ^
    --noconfirm ^
    AURA_APP\standalone.py

echo.
echo === Build completado ===
echo Ejecutable: dist\AURA OS.exe
pause
