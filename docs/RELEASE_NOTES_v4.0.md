# v4.0.0 Release Notes

**Release Date:** 2026-07-16
**Status:** Production Ready ✅

---

## 🎉 Highlights

v4.0 expands AURA/AME from a single-server web platform into a multi-surface,
multi-server, security-hardened AI ecosystem. This release bundles:

- **Admin Security** — JWT auth + RBAC + audit logging + rate limiting on the
  server-management API.
- **Multi-Server Support** — pluggable `ServerAdapter` framework (Local / Vercel
  / Railway / AWS) with live switch and DB sync.
- **React Native Mobile App** (`ame-mobile-rn/`) — Expo-based native client.
- **Fine-tuned AI pipeline** (`scripts/finetune-model.py`,
  `scripts/collect-training-data.py`) — Qwen2.5 fine-tuning + HuggingFace push.
- **Analytics Engine** (`scripts/analytics-engine.py`) — aggregation, anomaly
  detection and forecasting.
- **CI/CD hardening** — robust 3-job GitHub Actions workflow.

> Note: the mobile app, fine-tune pipeline and analytics engine were introduced
> in earlier Phase 58 tracks; v4.0 formalizes them under a single release and
> adds the security + multi-server layer that makes the platform production-grade.

---

## 🔐 Admin Security (NEW)

- JWT authentication for the admin API (`ame_backend/src/lib/auth.py`).
- RBAC: `admin` and `viewer` roles with per-permission grants.
- Audit logging of every admin action to `admin_audit.log` + stdout.
- Rate limiting: 10 requests / 60s per user (HTTP 429 when exceeded).
- Token generation endpoint (`POST /api/admin/servers/generate-token`, admin only).
- Admin dashboard at `/admin/servers` (requires a bearer token).

### Endpoints (all require `Authorization: Bearer <jwt>`)
| Method | Path | Permission |
|--------|------|------------|
| GET | `/api/admin/servers` | `servers:read` |
| POST | `/api/admin/servers` (register/switch/deploy) | `servers:write` / `servers:switch` |
| PUT | `/api/admin/servers` (sync DB) | `servers:sync` |
| GET | `/api/admin/servers/audit-logs` | `audit:read` |
| POST | `/api/admin/servers/generate-token` | admin only |

Verified locally: no-auth → 401, admin → 200, viewer-on-write → 403, 11th request → 429.

---

## 🖥️ Multi-Server Support (NEW)

- `ServerAdapter` base class + `LocalAdapter`, `VercelAdapter`, `RailwayAdapter`,
  `AWSAdapter` in `ame_backend/src/deployment/server_adapter.py`.
- `ServerManager` singleton: register, health-check, **switch without downtime**
  (only flips active target after the new target passes a health check), and
  `sync_all` DB synchronization.
- Frontend proxy + dashboard wired to the backend (`frontend/app/admin/servers`).

> Deploying to Vercel/Railway/AWS requires real platform tokens. The Local
> target works out of the box.

---

## 📱 React Native Mobile App

`ame-mobile-rn/` — Expo-based iOS/Android client (Firebase Auth, real-time chat,
offline-first queue). See that directory for setup.

## 🧠 Fine-tuned AI Model

`scripts/collect-training-data.py` + `scripts/finetune-model.py` — collect
conversations, fine-tune Qwen2.5 (LoRA), push to HuggingFace Hub.

## 📊 Analytics Engine

`scripts/analytics-engine.py` — real-time aggregation, ML anomaly detection
(Isolation Forest) and 7-day forecasting.

## 🔄 CI/CD Improvements

`.github/workflows/auto-deploy.yml` split into three jobs:
- `frontend-checks`: `typecheck` + `lint:local` + `test`.
- `backend-checks`: `compileall` + live `/health` and `/api/admin/servers` smoke.
- `deploy`: Vercel-only, gated to `main` pushes (no local `next build`, which the
  pinned `next@9` cannot run against the App Router).

---

## 📈 Stats (this release)

- **Tests:** 7 passing / 3 skipped / 0 failures (frontend).
- **TypeScript / lint errors:** 0 (via `tsconfig.local.json` + `eslint.local.mjs`).
- **Python:** all `ame_backend` modules compile (`py_compile`).
- **Endpoints added:** admin server API (5 routes) + multi-server framework.

---

## 🛠️ Technical Stack

- **Frontend:** Next.js (App Router) on Vercel.
- **Mobile:** React Native (Expo), Firebase.
- **Backend:** FastAPI (Python) + uvicorn.
- **AI:** Qwen2.5 (fine-tunable, LoRA).
- **Analytics:** pandas, scikit-learn.
- **Auth:** JWT (HS256) + RBAC.
- **Deploy:** Vercel / Railway / AWS (multi-server ready).

---

## 📦 Installation & Setup

```bash
# Backend + local runtime (autonomous)
.\scripts\autonomous-setup.ps1

# Generate an admin token for local testing
.\scripts\generate-admin-token.ps1

# Mobile
cd ame-mobile-rn && npm install && expo start

# Analytics
python scripts/analytics-engine.py --compute-daily
```

---

## 🔗 URLs

- **Web:** https://aura-web-chi-seven.vercel.app
- **Backend Local:** http://localhost:8000
- **Health:** http://localhost:8000/health
- **Admin API:** http://localhost:8000/api/admin/servers (JWT required)
- **Swagger:** http://localhost:8000/docs

---

## 🚨 Known Issues & Limitations

1. **Frontend local dev** needs Next.js 13+ (`next@9.3.3` is pinned and cannot
   run the App Router locally). Use Vercel for dev/preview.
2. **Multi-server deploy** needs platform tokens (Vercel/Railway/AWS) — framework
   is ready, awaiting credentials.
3. **Admin API** should sit behind a real reverse proxy / network ACL in
   production; the built-in rate limiter is per-process only.

---

## 📚 Documentation

- `README.md`, `CHANGELOG.md`, `RELEASE_NOTES_v4.0.md`
- `MARKETPLACE_TOOLS.md`, `FINAL_REPORT_PHASE58.md`, `PHASE_58_PROGRESS.md`
- `AUTONOMOUS_SETUP.md`, `LOCALHOST_SETUP.md`, `RAILWAY_SETUP_GUIDE.md`

---

## 🙏 Credits

- **Kilo:** infrastructure, multi-server framework, JWT security, CI/CD.
- **Raiden:** architecture, direction, review.
- **Cline:** earlier Phase 58 tracks (mobile, fine-tune, analytics).

---

**Thank you for using AURA/AME v4.0! 🎉**
