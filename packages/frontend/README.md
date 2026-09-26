# AURA/AME v3.0 — Asistente IA Empresarial

> Dashboard de integraciones empresariales para AME, con analytics, seguridad
> endurecida, monitoreo 24/7 y calidad de código verificable.

## Qué es

AURA/AME es un asistente IA con un dashboard web (Next.js App Router) que
conecta AME con las plataformas de tu equipo:

- 💬 **Slack** — comandos `/ame analyze`, `/ame news`
- 🎮 **Discord** — bot con comando `/ame`
- ✈️ **Telegram** — chat directo con el bot
- 👥 **Microsoft Teams** — app para equipos
- 🔗 **Webhooks Custom** — integración vía `POST /api/webhooks`
- 📊 **Analytics Dashboard** — `/analytics` (eventos, integraciones, latencia)

## 🎯 Features

### 🔗 5 Enterprise Integrations

1. **Slack** — usa `/ame analyze <texto>` en cualquier canal.
   ```bash
   /ame analyze "What's the best approach for caching?"
   → AME responde con el análisis
   ```
2. **Discord** — el bot responde al comando `/ame`.
   ```
   /ame What's my AME status?
   → Respuesta con tarjeta
   ```
3. **Telegram** — interfaz de chat directo (`@ame_bot`).
4. **Microsoft Teams** — app integrada al workspace (`@AURA` en chat).
5. **Webhooks** — integraciones custom (ver API más abajo).

### 📊 Analytics Dashboard (`/analytics`)

- Seguimiento de eventos en tiempo real (consume `/api/logs`).
- Monitoreo del estado de integraciones (`/api/integrations/status`).
- Tasa de errores + latencia promedio de API.
- Desglose de eventos por categoría + lista de eventos recientes.
- Visita: `https://aura-web-chi-seven.vercel.app/analytics`

### 🔐 Security Features

- ✅ Autenticación bearer (`API_SECRET_KEY`) en `/api/webhooks` y `/api/logs`.
- ✅ Validación SSRF en `/api/webhooks` (bloquea loopback/privadas).
- ✅ CORS configurado para `/api/*`.
- ✅ Logging centralizado (`/api/logs`).

### ⚡ Developer Experience

- Retry automático con exponential backoff (`lib/fetch-retry.ts`).
- Error boundaries en UI + loading skeletons.
- TypeScript estricto.
- Tests con `node:test` (sin Jest/Playwright pesados).

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/raidenia3-oss/AURA-server.01.git
cd AURA-server.01/frontend
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env.local
# Edita .env.local con tus valores (ver sección Configuración)
```

### 3. Run Development

```bash
npm run dev
# Abre http://localhost:3000
```

### 4. Visit Dashboards

- **Integrations:** http://localhost:3000/integrations
- **Analytics:** http://localhost:3000/analytics
- **Health Check:** http://localhost:3000/api/health

### 5. Deploy to Vercel

```bash
git push origin main
# → Auto-deploy a https://aura-web-chi-seven.vercel.app
```

## Instalación

```bash
git clone https://github.com/raidenia3-oss/AURA-server.01.git
cd AURA-server.01/frontend
npm install
```

## Desarrollo local

El `package.json` fija `next` en una versión antigua para el entorno de
despliegue, pero el código usa APIs modernas de Next (App Router,
`next/server`). Por eso los comandos estándar `npm run lint` / `tsc` fallan
localmente. Usa en su lugar los scripts de verificación local:

```bash
npm run typecheck   # tsc -p tsconfig.local.json --noEmit (con shims)
npm run lint:local  # eslint -c eslint.local.mjs .
npm test            # node --test (logger, webhook-manager, smoke)
```

## Configuración (variables de entorno)

Crea `frontend/.env.local` (ver `frontend/.env.example`):

```bash
# CORS: origen permitido para las rutas /api/*
NEXT_PUBLIC_SITE_URL=https://aura-web-chi-seven.vercel.app

# Bearer secret para /api/webhooks y /api/logs (si no está seteado, quedan abiertos en dev)
API_SECRET_KEY=tu_secret_key_aqui

# Integraciones (cada una enciende su status cuando está presente)
SLACK_CLIENT_ID=xoxb-...
SLACK_REDIRECT_URI=https://tu-app/api/slack/install
DISCORD_TOKEN=...
TELEGRAM_TOKEN=...
TEAMS_APP_ID=...

# Monitoreo 24/7
NEXT_PUBLIC_API_URL=https://aura-web-chi-seven.vercel.app
```

> **Nota de seguridad:** cuando `API_SECRET_KEY` NO está configurado,
> `/api/webhooks` y `/api/logs` quedan abiertos (modo dev). En producción
> define la variable para exigir el bearer token.

## 📡 API Endpoints

### Health Check

```bash
GET /api/health
# → {"ok":true,"timestamp":"...","routes":[...]}
```

### Webhooks

```bash
# Listar webhooks (requiere API_SECRET_KEY cuando está configurado)
curl https://aura-web-chi-seven.vercel.app/api/webhooks \
  -H "Authorization: Bearer $API_SECRET_KEY"

# Registrar webhook (valida la URL y bloquea SSRF)
curl -X POST https://aura-web-chi-seven.vercel.app/api/webhooks \
  -H "Authorization: Bearer $API_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"id":"wh1","url":"https://your-service.com/webhook","events":["message"]}'

# Disparar webhooks suscritos a un evento
curl -X POST https://aura-web-chi-seven.vercel.app/api/webhooks \
  -H "Authorization: Bearer $API_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"event":"message","data":{"hello":1}}'

# Eliminar
curl -X DELETE "https://aura-web-chi-seven.vercel.app/api/webhooks?id=wh1" \
  -H "Authorization: Bearer $API_SECRET_KEY"
```

### Logs

```bash
# Obtener logs (requiere API_SECRET_KEY cuando está configurado)
curl "https://aura-web-chi-seven.vercel.app/api/logs?limit=100" \
  -H "Authorization: Bearer $API_SECRET_KEY"

# Respuesta:
# { "logs": [ { "ts":"...", "level":"info", "category":"integration",
#               "message":"...", "meta":null }, ... ] }
```

### Estado de integraciones

```bash
GET /api/integrations/status
# → {"slack":{"connected":true},"discord":{"connected":true},
#    "telegram":{"connected":true},"teams":{"connected":true},
#    "webhooks":{"connected":false,"count":0}}
```

## Seguridad

- ✅ **Webhooks protegidos** por API key (cuando `API_SECRET_KEY` está seteado).
- ✅ **Validación SSRF** en `/api/webhooks` (rechaza `localhost`, `127.0.0.1`,
  `0.0.0.0`, `::1`, `.local` y rangos `10.x` / `192.168.x` / `172.16-31.x` /
  `169.254.x`).
- ✅ **CORS** configurado en `next.config.js` para `/api/*`.
- ✅ **Logs protegidos** con el mismo bearer.
- ⚠️ **Rate limiting** implementado en `ame-core` (`lib/rateLimit.ts`); aún no
  está aplicado a las rutas de integraciones (ver `MEJORAS-FASE-57.md`).

## Testing

```bash
npm test          # node:test (logger + webhook-manager + smoke HTTP)
npm run typecheck # verificación de tipos local
npm run lint:local# lint local (parser @typescript-eslint)
```

Los smoke tests HTTP solo corren si defines `BASE_URL` (p.ej. contra un
despliegue vivo); se skipean localmente.

## Deployment

Despliegue automático en Vercel al hacer push a `main` (rootDirectory:
`frontend`).

```bash
git push origin main
# → Auto-deploy a https://aura-web-chi-seven.vercel.app
```

## Monitoreo

```bash
node scripts/monitor-24-7.js
```

Verifica `/api/health`, `/api/integrations/status`, `/api/webhooks` y
`/api/ame-core` cada 5 minutos y alerta si algo falla. El script no arranca
solo al importarse (solo con `require.main === module`).
