# ARIA / AURA OS

## Zero-touch setup (recommended)

```bash
python aria_setup.py --auto-configure
python aria_autonomous.py
```

One command detects the host, installs dependencies, creates configuration,
initialises the database, builds the Rust crates and validates the result.
No prompts, no manual steps. Full reference: [docs/AUTO_SETUP.md](docs/AUTO_SETUP.md).

## Desktop build

1. **Double-click** `dist/AURA OS.exe`
2. Say: "Prendete" (or type in the chat box)
3. AURA activates, listens, and responds

## Requirements

- Windows 10/11
- No Python installation needed (standalone EXE)
- Ollama running with `dolphin-2_6-phi-2` model for local AI
- Atria API key in `.env` for enhanced intelligence (optional)

## Setup commands

```bash
python aria_setup.py --auto-configure    # full zero-touch setup
python aria_setup.py --validate          # health checks only
python aria_setup.py --diagnose          # explain current state
python aria_setup.py --reset             # clean rebuild
```

## Files

- `aria_setup.py` — Zero-touch configuration entry point
- `aria_autoconfig/` — Auto-configuration engine (12 modules)
- `aria_autonomous.py` — Autonomous self-improvement loop
- `docs/AUTO_SETUP.md` — Setup reference
- `dist/AURA OS.exe` — Main executable
- `AURA_APP/scripts/verify_all.py` — Pre-build verification
- `AURA_APP/scripts/build.py` — Build script
- `AURA_APP/desktop_ui.py` — PyQt5 UI with orb, chat, tray
- `AURA_APP/aria_logic_engine.py` — Logic engine (IPC)
- `AURA_APP/backend/aria_adaptive_engine.py` — Adaptive engine

## Verification Report

All 25 checks passed:
- Environment: ATRIA_API_KEY loaded
- Imports: PyQt5, Ollama, HTTPX, dotenv, LogicEngine, AdaptiveEngine, SkillRegistry, ToolRegistry, ReactLoop, ShortTermMemory, AIProviderManager, Atria Integration
- Config: .env exists
- Ollama: model found, response OK
- Atria: API connection OK
- Database: user_profile.json exists
- LogicEngine: instantiation OK
- AdaptiveEngine: intent detection OK
- PyQt5 UI: import OK
- Atria Integration: all modules importable
- Autonomy: importable
- E2E: flow OK

## Build Command

```powershell
.venv\Scripts\python.exe AURA_APP/scripts/build.py
```