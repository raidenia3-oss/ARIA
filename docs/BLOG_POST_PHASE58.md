# Building a Self-Hosting, Multi-Server AI Platform (AURA/AME)

*Draft blog post — Phase 58.*

We just shipped a batch of infrastructure work on AURA/AME that makes the
platform easier to run locally, safer to deploy, and able to move between
hosting providers without a rewrite.

## 1. One command to run it locally

An **autonomous config agent** now detects your environment (OS, Python, Node,
Git), writes the local `.env` files, installs dependencies, starts the backend
and verifies its health — all from a single script. No more copy-pasting
setup steps.

```powershell
.\scripts\autonomous-setup.ps1
```

## 2. Multi-server, no downtime

The new **ServerAdapter framework** treats every hosting target — Local,
Vercel, Railway, AWS — behind one interface: `connect`, `deploy`,
`health_check`, `sync_database`, `get_url`. A `ServerManager` registers targets,
checks their health, and switches the active one only when the new target is
healthy.

There's an admin API (`/api/admin/servers`) and a small dashboard to register a
provider (paste a token), see which targets are healthy, and flip the active
server live.

## 3. A CI pipeline that actually matches reality

We split CI into independent checks: the frontend runs typecheck + lint + tests,
the backend compiles and smoke-tests its `/health` and admin endpoints, and the
deploy step hands the build to Vercel (which uses a modern Next.js) instead of
failing on the pinned legacy version.

## 4. A bug worth calling out

While wiring the admin API, we found that mounting a sub-app at `/` was silently
shadowing every route added after it — which had already broken the
browser-control skill. Fixing the mount order brought both features back to life.

## What's next

Real deploys against Vercel/Railway with live tokens, the Phase 58 analytics
dashboard, and the mobile app (`ame-mobile-rn`).
