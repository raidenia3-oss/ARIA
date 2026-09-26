# AURA/AME v4.0: From Single-Server Web to a Secure, Multi-Server AI Platform

**TL;DR:** v4.0 hardens AURA/AME with JWT + RBAC security, a pluggable
multi-server deployment framework, a React Native app, a fine-tunable AI
pipeline and an ML analytics engine — all open source and production-ready.

---

## What v4.0 Actually Ships

We took the v3.0 web platform (5 integrations, real-time analytics, 24/7
monitoring) and made it **production-grade** in three moves:

### 1. Admin Security (JWT + RBAC)

Every privileged operation on the server-management API is now authenticated
and audited.

```bash
# Mint a local dev token
.\scripts\generate-admin-token.ps1

# All admin calls need it
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/admin/servers
# -> 200 with the server list

# No token? 401. Viewer touching a write action? 403. Too fast? 429.
```

- **JWT (HS256)** validation via `ame_backend/src/lib/auth.py`.
- **RBAC**: `admin` (full) vs `viewer` (read + audit) roles.
- **Audit log**: every action written to `admin_audit.log`.
- **Rate limiting**: 10 req / 60s per user.

### 2. Multi-Server Support

Switch hosting targets without downtime:

```python
from ame_backend.src.deployment.server_adapter import ServerManager, ServerType

manager = ServerManager()
manager.register_server(ServerType.RAILWAY, credentials)
# Only flips active after the target passes a health check
manager.switch_server(ServerType.RAILWAY)
```

Adapters for **Local, Vercel, Railway and AWS** implement one interface, so
adding a provider is a single new class. DB sync propagates across registered
targets.

### 3. Vertical Features (from earlier Phase 58 tracks)

- **React Native app** (`ame-mobile-rn/`): Expo + Firebase, offline-first.
- **Fine-tuned AI**: `scripts/finetune-model.py` + `scripts/collect-training-data.py`
  (Qwen2.5, LoRA, HuggingFace push).
- **Analytics engine**: `scripts/analytics-engine.py` (aggregation, Isolation
  Forest anomaly detection, 7-day forecasting).

---

## Why It Matters

- **Safe to expose**: admin actions can't be performed by anonymous callers
  anymore — the critical gap from v3.0 is closed.
- **Portable**: move between Vercel, Railway and AWS without rewriting code.
- **Auditable**: who did what, when, is logged.
- **CI-verified**: typecheck + lint + tests on the frontend, compile + health
  smoke test on the backend, before any Vercel deploy.

---

## By The Numbers

```
Tests:        7 passing / 3 skipped / 0 failures
TS/Lint:      0 errors (local tsconfig + eslint shims)
Python:       all ame_backend modules compile
Endpoints:    admin server API (5 routes) + multi-server framework
Backward:     v3.0 fully compatible
```

---

## Get Started

```bash
# Backend + local runtime (autonomous)
.\scripts\autonomous-setup.ps1

# Mobile
cd ame-mobile-rn && npm install && expo start

# Fine-tune
python scripts/collect-training-data.py --output data.jsonl
python scripts/finetune-model.py --epochs 3
```

Repo: https://github.com/raidenia3-oss/AURA-server.01 — MIT licensed.

---

**Now go build something with AURA/AME v4.0.** 🚀
