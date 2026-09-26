# ARIA OS v4.0

Asistente Virtual Inteligente — AI-Driven, no scripts.

## Quick Start

```bash
# Solo di "Prendete"
python AURA_APP/aria_startup.py

# O usa el auto-fix
python AURA_APP/auto_fix_bundle.py
```

## Features

- **Auto-startup**: Solo "Prendete" y ARIA se activa
- **USB Detection**: Detecta USB y expande almacenamiento automáticamente
- **Adaptive Learning**: Aprende del usuario sin intervención manual
- **AI-Driven**: Pura IA, no scripts
- **PStack Integration**: Orquestador de flujos automático
- **5 OSS Repos**: Headroom, Claude Context, Agent-skills, Agency-agents, Skill Recorder

## Architecture

```
ARIA_v4/
├─ AURA_APP/
│  ├─ backend/logic/    → Logic, Adaptive, Intent, IPC
│  ├─ backend/intelligence/ → AriaBrain (8 submódulos)
│  ├─ backend/integration/  → 5 OSS repos
│  ├─ backend/expansion/    → USB, Models, Cache
│  ├─ backend/api/          → FastAPI routes
│  ├─ backend/learning/     → Memory, Behavior, Adaptive
│  ├─ backend/storage/      → SQLite, Profile, Skills
│  ├─ ui/                   → Desktop UI (PyQt5)
│  └─ tests/                → verify_system.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/aria/chat | Chat con ARIA |
| GET | /api/aria/usb/status | Estado USB |
| POST | /api/aria/usb/expand | Expandir con USB |
| POST | /api/aria/auto | ARIA automática |
| POST | /api/aria/pstack/potato-mode | PStack potato mode |
| GET | /api/aria/pstack/blast-radius/{change} | Blast radius |
| GET | /api/system/health | Health check |

## Development

```bash
pip install -r requirements.txt
pytest AURA_APP/tests/ -v
```

## Build

```bash
pip install PyInstaller
pyinstaller --onefile --windowed AURA_APP/aria_main.py
```

## Troubleshooting

- **PyQt5 not found**: `pip install PyQt5`
- **USB not detected**: Check OS permissions
- **Memory high**: Run `python AURA_APP/auto_fix_bundle.py`
