# AURA Autonomous Setup Agent

A `config_agent` that detects the environment, creates the local `.env` files,
installs Python dependencies, starts the backend and verifies its health — with
no manual steps.

## Quick Start

### Windows (PowerShell)
```powershell
.\scripts\autonomous-setup.ps1
```

### macOS / Linux
```bash
./scripts/autonomous-setup.sh
```

## What it does

1. **Detects environment** — OS, Python, Node.js, Git.
2. **Creates config** — `frontend/.env.local.dev`, `backend/.env.local`,
   `ame_backend/.env.local` (SQLite + dev secrets). Vercel `.env.local` is
   never touched.
3. **Installs Python deps** — `pip install -r` for `backend/` and
   `ame_backend/`.
4. **Starts the backend** — `python -m ame_backend.src.main` on `:8000`
   (run as a module so package imports resolve).
5. **Verifies health** — polls `http://localhost:8000/health` (200 OK).

## URLs after setup

- Backend (Local): http://localhost:8000
- Backend (WiFi): http://<your-ip>:8000
- Health Check: http://localhost:8000/health

## Notes / limitations

- The frontend (Next.js) needs **Next 13+** for the App Router code. The
  currently installed `next` is `9.3.3`, so the agent only *checks* the
  frontend and does not launch it locally. The frontend stays on Vercel:
  https://aura-web-chi-seven.vercel.app
- The agent keeps the backend process alive until you press `Ctrl+C`.
- Health route is `/health`, **not** `/api/health`.

## Troubleshooting

### ModuleNotFoundError on backend start
The agent already runs `python -m ame_backend.src.main`. If you run it
manually, use the module form, never `python ame_backend/src/main.py`.

### Port 8000 already in use
```powershell
Get-Process python | Stop-Process -Force
```

### Health check returns 404
Use `/health`, not `/api/health`.
