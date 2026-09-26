# 🔧 MEJORAS-FASE-57.md — Auditoría de Funciones (Fase 57)

**Fecha:** 2026-07-13
**Autor:** Kilo (auditoría de la app web Next.js `frontend/`)
**Alcance:** `frontend/` (app AME / Integraciones). El backend Flask de
`AURA_OS_Workspace/` ya está auditado en `AURA_OS_Workspace/PENDING_TASKS_AUDIT.md`
(no se duplica aquí).

> **Nota de entorno:** `node_modules/next` está resuelto como v9.3.3 pero el código
> usa App Router / `next/server` / `next/font/google`. Eso rompe `tsc` y `eslint`
> estándar. Ya existe un workaround local: `tsconfig.local.json` + `eslint.local.mjs`
> + `types/next-shims.d.ts` (ver `npm run typecheck` / `npm run lint:local`).

---

## 1. Funciones que faltan en v2.0

- [ ] **Autenticación de usuarios completa** — Solo existe el helper
      `lib/authenticate.ts` (Bearer vs `API_SECRET_KEY`) y se usa **solo** en
      `app/api/ame-core/route.ts`. No hay login UI, sesiones, ni protección en la
      mayoría de rutas. `next-auth` ya es dependencia pero no está cableado.
- [ ] **Persistencia de datos** — Status de integraciones, API keys, webhooks y
      logs viven en memoria (`WebhookManager` usa `Map`; `logger.js` usa array).
      En serverless (Vercel) ese estado se pierde entre invocaciones.
- [ ] **Caché** — Solo `cache-control: no-store` en `/api/health`,
      `/api/integrations/status` y `/api/logs`. Sin revalidación ni cache de
      respuestas.
- [ ] **Rate limiting avanzado** — `lib/rateLimit.ts` existe pero **solo se usa en
      `ame-core`**. No está en `/api/webhooks`, `/api/logs`, `/api/slack/install`,
      etc.
- [ ] **Analytics dashboard** — No existe (Fase 58, Opción F).
- [ ] **Admin panel / Settings / Preferences de usuario** — No existen.
- [ ] **Error boundaries / Loading states** — No hay `error.tsx` ni `loading.tsx`
      en `app/` (glob confirmado: 0 coincidencias).
- [ ] **CORS configurado** — `next.config.js` no define `async headers()`; las
      rutas no setean `Access-Control-*` (grep confirmado).

---

## 2. Bugs / issues conocidos

- 🔴 **`/api/webhooks` sin autenticación** — Cualquiera puede `POST` registrar un
      webhook o disparar `trigger` (que hace `fetch` a URLs arbitrarias desde el
      servidor). Riesgo de abuso / SSRF-lite. `app/api/webhooks/route.ts`.
- 🟡 **`/api/logs` expuesto si no hay `LOG_VIEW_TOKEN`** — Devuelve logs en claro
      cuando la variable no está seteada (`app/api/logs/route.ts:13`).
- 🟡 **Comparación de token no constante** — `authenticate` usa `!==` directo
      (timing attack menor). Usar `crypto.timingSafeEqual`.
- 🟡 **`rateLimit` no sirve en serverless** — Usa `Map` en memoria (estado no
      compartido entre lambdas). Además `getIP` cae a `x-real-ip`, spoofeable.
- 🟡 **Dashboard silencia errores de fetch** — En `/integrations`
      `fetchStatus().catch(() => setStatus(null))` muestra todo "Desconectado" sin
      indicar que hubo un error, y no hay spinner de carga mientras espera.
- 🟡 **Cobertura de tests limitada** — Solo `node:test` para `logger` y
      `webhook-manager` + smoke tests (skipped sin `BASE_URL`). No hay tests de
      componentes UI ni de rutas API.
- 🟡 **Lint roto en CI** — `npm run lint` (`eslint .`) falla por archivos legacy
      (`lib/discord-bot.js`, `lib/slack-bot.js`, `lib/teams-bot.js`,
      `lib/auto-learning-engine.js`: `require()` + unused vars). No son archivos
      míos pero bloquean el lint global.
- 🟢 **Mismatch de versión de Next** — `package.json` fija `^9.3.3`; el código
      requiere Next 13+. Ver nota de entorno arriba.

---

## 3. Mejoras rápidas (< 30 min) — HACER AHORA (Fase 57.5)

- [ ] **Loading state en `/integrations`** — Skeleton/spinner mientras carga
      `status` (estado `status === null` hoy no se distingue de "desconectado").
- [ ] **Error boundary + retry** en el fetch de status — Mostrar error claro +
      botón "Reintentar" (hoy el `.catch` oculta el fallo).
- [ ] **Toast notifications** para "Key copiada", "Webhook creado", errores.
- [ ] **Mensajes de error claros** al validar la URL del webhook (en
      `createWebhook`, `app/integrations/page.tsx`).
- [ ] **Aplicar `rateLimit` + `authenticate`** a `POST /api/webhooks` (al menos
      `register`) y forzar `LOG_VIEW_TOKEN` en `/api/logs`.
- [ ] **`crypto.timingSafeEqual`** en `lib/authenticate.ts`.

---

## 4. Mejoras medianas (30 min – 2 h) — PRÓXIMA SEMANA

- [ ] **CORS en `next.config.js`** (`async headers()`) para callbacks de
      Slack/Discord/Teams y webhooks cross-origin.
- [ ] **Validación con `zod`** del body en `POST /api/webhooks` (ya es dependencia
      transitiva en `package-lock.json`).
- [ ] **Persistencia de webhooks/logs** en KV externo (Upstash Redis / Vercel KV)
      en vez de `Map`/array en memoria.
- [ ] **Rate limiting distribuido** (Upstash Ratelimit) para que funcione en
      serverless.
- [ ] **Cache de respuestas API** — `cache-control` adecuado + `revalidate` donde
      aplique.
- [ ] **Arreglar o excluir** los archivos legacy del lint y cablear
      `npm run lint:local` en CI.
- [ ] **Tests de rutas API** usando mocks de `next/server` para
      `status` / `webhooks` / `logs`.

---

## 5. Mejoras grandes (> 2 h) — ROADMAP (Fase 58)

- [ ] **Auth completa** (login, sesiones, RBAC por usuario) — cablear `next-auth`.
- [ ] **Persistencia de estado de integraciones + API keys por usuario** (DB).
- [ ] **Analytics dashboard** completo (Fase 58, Opción F).
- [ ] **React Native / mobile app** (Fase 58, Opción A).
- [ ] **IA avanzada**: fine-tuning + multimodal (Fase 58, Opción D).
- [ ] **i18n**, **dark mode toggle**, **accesibilidad WCAG**, **PWA offline-first
      avanzado**.
- [ ] **CI/CD GitHub Actions** con `node --test` + Playwright + Lighthouse.

---

## Resumen de prioridad

| Área            | Estado actual (web)        | Riesgo | Siguiente paso               |
|-----------------|----------------------------|--------|------------------------------|
| Auth            | Helper solo en ame-core    | Alto   | Fase 57.5 + next-auth        |
| Webhooks        | Sin auth / sin validación  | Alto   | Fase 57.5 (auth+rate limit)  |
| Logs            | Expuestos sin token        | Medio  | Fase 57.5 (forzar token)     |
| UX dashboard    | Sin loading/error/toast    | Bajo   | Fase 57.5 (quick wins)       |
| CORS / cache    | Ausentes                   | Medio  | Fase 4 (mediana)             |
| Tests / lint    | Limitados / rotos global   | Medio  | Fase 4 (mediana)             |
| Persistencia    | En memoria (pierde estado) | Alto   | Fase 4 (KV externo)          |

**Orden sugerido:** Fase 57.5 (quick wins, < 2 h) → Fase 4 medianas → luego
Fase 58 (grandes, paralelo A+D+F).
