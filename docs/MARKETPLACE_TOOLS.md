# AURA/AME Marketplace — Tool Audit

Audit of useful tooling **already present** in this repository. No external
installs were performed (per plan: audit + document only).

Selection criteria: reused across tracks, low friction, high leverage for
local dev, deployment, monitoring and the Phase 58 roadmap (mobile, fine-tuning,
analytics).

## Top 5 tools

### 1. `scripts/autonomous-setup.ps1` / `.sh` — Autonomous Config Agent
- **What:** launches `ame_backend/src/automation/config_agent.py`, which detects
  OS/Python/Node/Git, writes the local `.env` files, installs Python deps and
  starts the backend, then verifies `/health`.
- **Why useful:** one command to bring the backend up locally with zero manual
  config. Already validated (backend reaches `200` on `/health`).
- **Use:** `.\scripts\autonomous-setup.ps1` (Windows) or
  `./scripts/autonomous-setup.sh` (mac/Linux).

### 2. `scripts/start-localhost.ps1` + `scripts/check-local.ps1` — Local runtime
- **What:** start script runs `ame_backend` on `:8000` (as a module) and the
  frontend dev server; the health-check script probes frontend/backend and
  prints the local WiFi IP.
- **Why useful:** clean local dev loop with health verification; safe (never
  touches the Vercel `.env.local`).
- **Use:** `.\scripts\start-localhost.ps1` then `.\scripts\check-local.ps1`.

### 3. `scripts/monitor-integrations.js` — Integration monitor
- **What:** polls `/api/health`, `/api/ame-core`, Slack/Discord/Telegram/Teams
  webhooks every 5 minutes and reports failures.
- **Why useful:** 24/7 awareness of which integration is down without opening
  a dashboard. Pairs with `monitor-24-7.js`.
- **Use:** `node scripts/monitor-integrations.js` (set `NEXT_PUBLIC_API_URL`).

### 4. `scripts/collect-training-data.py` + `scripts/finetune-model.py` — Phase 58 ML
- **What:** collect interaction/feedback data into `training-data.jsonl` and a
  fine-tuning launcher (HuggingFace `QWEN_URL`).
- **Why useful:** the data flywheel for the Phase 58 fine-tuning roadmap; already
  scaffolded and part of `git status`.
- **Use:** `python scripts/collect-training-data.py` then
  `python scripts/finetune-model.py`.

### 5. `scripts/analytics-engine.py` + `frontend/app/api/analytics/route.ts` — Analytics
- **What:** Python analytics engine plus a Next.js API route for events.
- **Why useful:** foundation for the Phase 58 analytics dashboard without a
  third-party provider.
- **Use:** extend the route + engine; wire the dashboard later.

## Also present (honorable mentions)
- **Deploy:** `deploy.sh`, `setup-railway.sh`, `setup-vercel.sh`,
  `vercel-deploy.js` — Vercel/Railway wiring (Railway commands already validated
  in `setup-railway.sh`).
- **n8n:** `setup-n8n.sh`, `validate_n8n_workflow_final.ps1` — automation
  workflows.
- **Browser control skill:** `frontend/app/skills/browser-control`,
  `ame_backend/src/automation/browser_control.py`,
  `ame_backend/src/api/skills_browser_control.py` — AURA/AME control over the
  browser + device-app bridge via `BroadcastChannel`.
- **Mobile scaffold:** `ame-mobile-rn/` — React Native app (Login/Signup,
  Chat, AMEs list, Settings) talking to `/api/mobile/*`.
- **CI:** `.github/workflows/auto-deploy.yml` — test + Vercel deploy + release.

## Notes / gaps
- The frontend cannot run locally with the installed `next@9.3.3` (App Router
  needs Next 13+); it deploys on Vercel. Documented in `LOCALHOST_SETUP.md`.
- `Jupyter AI MCP` (requested earlier) is **not installed** — it needs
  `pip install jupyter-ai-mcp` plus an LLM provider, and registration in
  `kilo.jsonc`. Left out of this audit per the "no installs" scope.
- The marketplace is currently **repo-internal**; there is no external package
  registry. These are project scripts/modules, not installable plugins.
