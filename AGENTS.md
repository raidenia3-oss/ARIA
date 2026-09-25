# AURA OS v2.0 — Instrucciones de Desarrollo

## Build (Windows — PowerShell)
```powershell
cd C:\Users\User\Downloads\AURA
# ARIA OS v4.0 — Desktop Standalone (sin HTTP, sin servidores)
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

### Ejecución v4.0 (Standalone Desktop)
```powershell
# Sin servidor HTTP — desktop nativo con IPC interna
.venv\Scripts\python.exe AURA_APP\aria_main.py
```

## Start / Stop / Status
```powershell
.\aura-os\scripts\start-aura-app.ps1 -Exe      # Lanza dist\AURA OS.exe
.\aura-os\scripts\start-aura-app.ps1            # Lanza con python (dev)
.\aura-os\scripts\start-aura-app.ps1 -Stop
.\aura-os\scripts\start-aura-app.ps1 -Status
```

## Validación rápida
```powershell
curl.exe -s http://localhost:8000/health
curl.exe -s http://localhost:8000/api/system/status
curl.exe -s http://localhost:8000/chat/tools | ConvertFrom-Json | Measure-Object
```

## ARIA OS v5.0 (Electron + React + Three.js) — en `v5/`
```powershell
cd C:\Users\User\Downloads\AURA\v5
npm install            # deps (React 19, Three, Electron 31, framer-motion, zustand)
npm run dev            # Vite + Electron (auto-start del backend FastAPI v4 en :8000)
npm run typecheck      # tsc --noEmit
npm run build          # dist/ (renderer) + dist-electron/ (main + preload)
npm run build:exe      # electron-builder --win → release/ (NSIS + portable)
```
- Backend: `ARIA_APP/backend/app.py` vía `uvicorn app:app --port 8000` (spawn del main process).
- IPC: `chat:send`, `skills:load`, `system:status`, `settings:get|set` (userData/settings.json), `window:*`.
- HUD: header glass + orb 3D (7 capas/12 partículas/anillos/bursts) + chat markdown + skills sidebar + centro de control.
- Detalles y limitaciones: `v5/README.md`.

## Estructura clave
- `AURA_APP/frontend/index.html` — HUD glassmorphic (25 skills, 10 tools)
- `AURA_APP/backend/` — FastAPI backend, skills registry (imports estáticos)
- `AURA_APP/frontend/index.html` — HUD glassmorphic
- `dist/AURA OS.exe` — ejecutable standalone (337MB)
