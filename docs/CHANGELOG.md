# Changelog

All notable changes to AURA/AME will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [4.0.0] - 2026-07-16

### Added
- **Admin Security** (JWT + RBAC) — `ame_backend/src/lib/auth.py`
  - JWT (HS256) auth on the server-management API
  - Roles `admin` / `viewer` with per-permission grants
  - Audit logging of all admin actions (`admin_audit.log`)
  - Rate limiting (10 req / 60s per user → 429)
  - Token generation endpoint (`POST /api/admin/servers/generate-token`)
  - Admin dashboard at `/admin/servers` (requires bearer token)
- **Multi-Server Support** — `ame_backend/src/deployment/server_adapter.py`
  - `ServerAdapter` framework (Local / Vercel / Railway / AWS)
  - `ServerManager`: register, health-check, switch without downtime, DB sync
  - Admin API `/api/admin/servers` (list / register / switch / sync / audit)
  - Frontend proxy + `/admin/servers` dashboard
- **React Native Mobile App** (`ame-mobile-rn/`, Expo + Firebase, offline-first)
- **Fine-tuned AI pipeline** (`scripts/finetune-model.py`, `scripts/collect-training-data.py`)
- **Analytics Engine** (`scripts/analytics-engine.py`: aggregation, anomaly detection, forecasting)
- **CI/CD** — 3-job GitHub Actions (`frontend-checks`, `backend-checks`, `deploy`)

### Changed
- `app.mount("/", telemetry_app)` now runs **after** routers so admin + browser-control routes are not shadowed.
- `.github/workflows/auto-deploy.yml` reworked; removed the local `next build` step (pinned `next@9` cannot build the App Router).

### Fixed
- Browser-control skill 404 caused by root mount order.
- JWT clock-skew handling (`verify_iat: False` + `leeway`, `iat` issued 60s in the past).

### Performance
- Multi-server switch validated by a health check before flipping the active target.

---

## [3.0.0] - 2026-07-14

### Added

- 📊 **Analytics Dashboard** (`/analytics`)
  - Eventos totales, integraciones OK (x/5), webhooks, errores y latencia promedio
  - Gráfico por categoría de eventos (sin dependencias externas)
  - Lista de eventos recientes con timestamps
  - Banner de error + botón Reintentar (reutiliza `fetchWithRetry`)
  - Consume endpoints existentes: `/api/logs`, `/api/integrations/status`

### Improved

- v3.0 = v2.0 + Analytics Dashboard web funcional
- Cero dependencias nuevas (reutiliza `fetchWithRetry`, paleta AURA)

### Technical

- Verificado localmente: `npm run typecheck` ✓, `npm run lint:local` ✓, `npm test` ✓
- Quality gate: 7 passed / 3 skipped

### Status

- **Production Ready (web):** Next.js app + 5 integraciones + Analytics
- **Scaffold documentado:** React Native, Fine-tuning, Analytics engine (ver `README-ROADMAP.md`)
- Listo para Fase 58 cuando el agente Cline esté disponible

## [2.0.0] - 2026-07-13

### Added

- 🔗 **Integraciones empresariales**: Slack, Discord, Telegram, Microsoft Teams y Webhooks Custom.
- 📊 **Dashboard de integraciones** en `/integrations` (status dinámico, comandos, creación de webhooks, gestión de API key).
- 🔒 **Autenticación** en `/api/webhooks` y `/api/logs` vía bearer `API_SECRET_KEY` (cuando está configurado).
- ⚡ **Monitoreo 24/7** (`scripts/monitor-24-7.js`) con chequeo cada 5 min y alertas automáticas.
- 📝 **Logging exhaustivo** (`lib/logger.js`) expuesto en `GET /api/logs`.
- 🔄 **Retry automático** con exponential backoff (`lib/fetch-retry.ts`) usado en el dashboard.
- ⚠️ **Error boundary** (`app/integrations/error.tsx`) y ⏳ **loading skeleton** (`app/integrations/loading.tsx`).
- 🧪 **Tests con `node:test`** (sin Jest/Playwright): `lib/logger.js` y `lib/webhook-manager.ts` + smoke HTTP.

### Security

- ✅ **Validación SSRF** en `/api/webhooks` (bloquea loopback y rangos privados).
- ✅ **CORS headers** configurados en `next.config.js` para `/api/*`.
- ✅ **Auth en `/api/logs` y `/api/webhooks`** (cuando `API_SECRET_KEY` está seteado).
- ✅ **Comparación de token** vía helper `authenticate`/`requireAuth`.

### Improved

- UX del dashboard (loading states, error handling visible, retry).
- Calidad de código: `tsconfig.local.json` + `eslint.local.mjs` para verificar localmente a pesar del mismatch de versión de Next.
- Documentación completa (README, CONTRIBUTING, esta entrada).

### Fixed

- `/api/webhooks` sin autenticación → ahora requiere bearer en producción.
- `/api/logs` expuesto en claro → ahora protegido.
- Sin CORS → agregado en `next.config.js`.
- Errores silenciosos en el dashboard → ahora muestran banner de error + reintentar.

### Technical

- `next.config.js` con `headers()` para CORS.
- Scripts de verificación local: `npm run typecheck`, `npm run lint:local`, `npm test`.
- Sin auto-start en el monitor (corre solo con `require.main === module`).

## [1.0.0] - 2026-07-06

### Added

- **Firebase Auto Setup with Fallback**: Browser automation with automatic fallback to manual config
- **Google AI Studio Integration**: Article analysis with mock mode for development
- **Health Check API**: Endpoint at `/api/health` monitoring all services
- **Dashboard de Monitoreo**: Real-time UI at `/dashboard` with auto-refresh
- **Chrome Extension**: Complete browser extension with popup, background, and content scripts
- **Service Worker**: Offline support with caching strategy
- **SEO Optimizations**: robots.txt, sitemap.xml, meta tags
- **Security Headers**: CSP, HSTS, X-Frame-Options, and more
- **No-JS Fallback**: Functional page without JavaScript
- **GitHub Actions**: Automated deploy to Vercel
- **Godot Game Integration**: WebSocket-based reward system documentation

### Changed

- Improved setup script with multi-level error handling
- Enhanced next.config.js with security and performance optimizations
- Updated documentation structure

### Fixed

- Firebase browser automation crash ("Navigating frame was detached") with automatic fallback
- API error handling with graceful degradation
- Build cache now properly excluded from git

## [0.9.0] - 2026-07-05

### Added

- Initial project structure
- Basic API endpoints
- Firebase configuration templates
- News worker system
- Core agent orchestrator
