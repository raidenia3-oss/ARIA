# AURA OS — Quick Start

## 1. Prerequisites

- Python 3.11+
- Ollama with `dolphin-2_6-phi-2` model (for local AI)

```powershell
winget install Ollama.Ollama
ollama pull dolphin-2_6-phi-2
```

## 2. Run as Desktop App (v4.0 — Standalone)

```powershell
cd C:\Users\User\Downloads\AURA
dist\AURA OS.exe
```

Native desktop window — no browser, no HTTP server, no ports.

## 3. Run in Development (v4.0)

```powershell
cd C:\Users\User\Downloads\AURA
.venv\Scripts\python.exe AURA_APP\aria_main.py
```

## 4. Build EXE (PyInstaller)

```powershell
cd C:\Users\User\Downloads\AURA
.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name "AURA OS" ^
  --add-data "AURA_APP\frontend;frontend" ^
  --add-data "ai_providers.py;." ^
  --hidden-import ai_providers ^
  --hidden-import backend.skills --hidden-import backend.skills.registry ^
  --hidden-import backend.skills.system ^
  --hidden-import backend.skills.system.status --hidden-import backend.skills.system.time ^
  --hidden-import backend.skills.system.ping --hidden-import backend.skills.system.scan ^
  --hidden-import backend.skills.system.whois --hidden-import backend.skills.system.open ^
  --hidden-import backend.skills.system.volume --hidden-import backend.skills.system.lock ^
  --hidden-import backend.skills.system.apps --hidden-import backend.skills.system.screenshot ^
  --hidden-import backend.skills.system.memory ^
  --hidden-import backend.skills.web --hidden-import backend.skills.web.search ^
  --hidden-import backend.skills.web.weather ^
  --hidden-import backend.skills.files --hidden-import backend.skills.files.list ^
  --hidden-import backend.skills.files.read --hidden-import backend.skills.files.write ^
  --hidden-import backend.memory --hidden-import backend.memory.working ^
  --hidden-import backend.memory.short_term --hidden-import backend.memory.long_term ^
  --hidden-import backend.proactive.engine --hidden-import backend.evolution.engine ^
  --hidden-import backend.learning.compound --hidden-import backend.api.compat ^
  --hidden-import AURA_APP.desktop_ui ^
  --hidden-import AURA_APP.aria_logic_engine ^
  --hidden-import desktop_tray ^
  --hidden-import auto_start ^
  --hidden-import PyQt5 --hidden-import PyQt5.QtWidgets ^
  --hidden-import PyQt5.QtCore ^
  --hidden-import PyQt5.QtGui ^
  --collect-all fastapi --collect-all uvicorn --collect-all pywebview ^
  --noconfirm AURA_APP\aria_main.py
```

## 5. Verify (legacy HTTP mode, optional)

```powershell
curl.exe -s http://localhost:8000/health
curl.exe -s http://localhost:8000/api/system/status
```

## 6. Skills Disponibles (25)

### Sistema (14)
`status`, `time`, `ping`, `scan`, `whois`, `open`, `volume`, `screenshot`, `memory`, `lock`, `apps`, `control`, `explorer`, `code_exec`

### Web (4)
`search`, `weather`, `automation`

### Archivos (3)
`list`, `read`, `write`

### Cerebro (3)
`think`, `memory-query`, `connectors`

### Investigación (2)
`social-research`, `video-analyze`

### Nuevas capacidades v4.0:
- **control**: mouse, teclado, captura, tamaño pantalla (`pyautogui`)
- **explorer**: listar archivos, leer/escribir, árbol de directorios
- **code_exec**: ejecutar código Python en sandbox
- **automation**: automatización de navegador (`pip install playwright && playwright install chromium`)

## 7. Desktop Tray & Hotkey

- **Hotkey global**: `Ctrl+Shift+A` para abrir/summon HUD
- **Tray icon**: ícono AURA en bandeja del sistema con menú
- **Auto-start**: se registra automáticamente al iniciar

## 8. Tool Registry & Safety

- **Tool Registry**: 10 herramientas (4 nuevas: `control_pc`, `explorer`, `code_run`, `browser`)
- **Safety Filter**: patrones peligrosos bloqueados con confirmación

## 9. Auto-Start (Windows)

```powershell
.venv\Scripts\python.exe -c "from AURA_APP.auto_start import is_registered; print(is_registered())"
.venv\Scripts\python.exe -c "from AURA_APP.auto_start import register; register()"
.venv\Scripts\python.exe -c "from AURA_APP.auto_start import unregister; unregister()"
```
