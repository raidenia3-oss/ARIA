# Localhost Development Setup

Run AURA locally: `frontend` on `:3000`, `ame_backend` on `:8000`, no Docker, no
PostgreSQL (uses SQLite for local state). Vercel deployment is **untouched**.

## Quick Start

```powershell
# 1. Start both services (ame_backend :8000 + frontend :3000)
.\scripts\start-localhost.ps1

# 2. In another PowerShell window, verify health
.\scripts\check-local.ps1
```

Then open:
- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health
- WiFi (same network, from phone/tablet): http://<your-local-ip>:3000

## Known local limitations

- **Backend** must run as a package, not a script:
  `python -m ame_backend.src.main` (the startup script already does this).
  Its health route is `/health` (200) — there is no `/api/health`.
- **Frontend cannot run locally with the currently installed `next@9.3.3`.**
  The code uses the Next.js **App Router** (`app/`, `next/server`,
  `next/font/google`), which requires Next 13+. `npm run dev` fails with
  *"Couldn't find a `pages` directory"*. The frontend is deployed on Vercel,
  which builds it with a modern Next version. To run the frontend locally you
  must upgrade Next (`npm i next@latest`) — out of scope for this localhost
  setup. The backend below runs fine standalone.

## How the frontend knows the backend URL

`next dev` loads `.env.local` by default. To point the **local** frontend at
`localhost:8000` without touching the Vercel `.env.local`, the startup script
sets `NODE_ENV=development`. If you need to override the API base explicitly,
run the dev server with the dev env file:

```powershell
cd frontend
$env:NODE_ENV = "development"
npm run dev
```

The local config files set:
- `NEXT_PUBLIC_API_BASE=http://localhost:8000`
- `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`
- `DATABASE_URL=sqlite:///./aura.db`

## Config Files (all NEW, local-only)

| File | Purpose |
|------|---------|
| `frontend/.env.local.dev` | Local frontend config (localhost backend) — **not committed as active** |
| `backend/.env.local` | Local `backend/` service (SQLite, dev secrets) |
| `ame_backend/.env.local` | Local `ame_backend/` service (SQLite, dev secrets, FRONTEND_URL) |
| `frontend/.env.local` | **Vercel config — DO NOT TOUCH** (still points to Vercel) |

## Switching

**To Vercel (already deployed):** just push to `main`; nothing local to change.

**To Localhost:** run `.\scripts\start-localhost.ps1`.

## Troubleshooting

### Frontend won't start
```powershell
cd frontend
npm install
npm run dev
```

### Port 8000 already in use
```powershell
Get-Process python | Stop-Process -Force
```

### Backend import error (missing dep)
```powershell
cd ame_backend
pip install -r requirements.txt
```

### WiFi access not working
```powershell
ipconfig
# Find "IPv4 Address" and open http://<that-ip>:3000 from the other device.
# Ensure Windows Firewall allows inbound on ports 3000/8000.
```

### Reset Vercel env if accidentally changed
```powershell
git checkout frontend/.env.local
```
