# Troubleshooting Guide — AURA/AME v3.0

> Soluciones a problemas comunes de la app web (Next.js / Vercel). Para la
> Fase 58 (React Native, fine-tuning, analytics engine) ver `setup-phase-58.md`.

## Common Issues

### 1. Puerto 3000 en uso
**Error:** `EADDRINUSE: address already in use :::3000`

```bash
# Matar proceso en el puerto 3000
lsof -ti:3000 | xargs kill -9   # (Linux/macOS)
# Windows:
netstat -ano | findstr :3000    # luego taskkill /PID <pid> /F

# O usar otro puerto
npm run dev -- -p 3001
```

---

### 2. Errores de TypeScript
**Error:** `tsc: command not found` o errores de tipos

```bash
cd frontend
npm install
npm run typecheck   # tsc -p tsconfig.local.json --noEmit
```

> El `tsc` estándar falla porque el `next` local es una versión antigua; usa
> `npm run typecheck` (usa `tsconfig.local.json` + shims en `types/`).

---

### 3. Errores de ESLint
**Error:** muchos errores en `npm run lint`

```bash
# Usa el lint local (parser @typescript-eslint, sin next/babel)
npm run lint:local

# Autofix donde sea posible:
npx eslint -c eslint.local.mjs . --fix
```

> Los archivos legacy (`lib/discord-bot.js`, `lib/slack-bot.js`,
> `lib/teams-bot.js`, `lib/auto-learning-engine.js`) tienen errores conocidos
> (`require()` + unused vars). No son parte del core de v3.0 y se refactorizan
> en la Fase 58. No bloquean el despliegue de Vercel.

---

### 4. Tests fallando
**Error:** `npm test` retorna fallos

```bash
npm install
npm test                       # node --test tests/*.mjs
npm test -- tests/logger.test.mjs   # un archivo
```

> Los smoke tests HTTP (`tests/api.smoke.test.mjs`) se skipean salvo que
> definas `BASE_URL` apuntando a un servidor vivo.

---

### 5. `/api/webhooks` responde 401
**Error:** `POST /api/webhooks → 401 Unauthorized`

```bash
# Si API_SECRET_KEY está configurado, envía el bearer:
curl -X POST https://localhost:3000/api/webhooks \
  -H "Authorization: Bearer $API_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"id":"wh1","url":"https://example.com/webhook","events":["message"]}'
```

> Si `API_SECRET_KEY` NO está seteado, el endpoint queda abierto (modo dev).

---

### 6. `/api/logs` responde 401
**Error:** `GET /api/logs → 401 Unauthorized`

```bash
# Requiere el mismo bearer que webhooks (API_SECRET_KEY):
curl https://localhost:3000/api/logs?limit=100 \
  -H "Authorization: Bearer $API_SECRET_KEY"
```

> Nota: en v3.0 los logs se protegen con `API_SECRET_KEY` (no con
> `LOG_VIEW_TOKEN`, que era el mecanismo anterior).

---

### 7. Dashboard de integraciones en blanco
**Error:** `/integrations` carga pero no muestra las cards

```bash
curl http://localhost:3000/api/integrations/status
# Debe devolver JSON con slack/discord/telegram/teams/webhooks
```

> Si el fetch falla, el dashboard muestra un banner de error + botón
> "Reintentar" (usa `fetchWithRetry` con backoff). Revisa la consola del
> navegador (F12) para errores de red.

---

### 8. Analytics sin datos
**Error:** `/analytics` carga pero muestra "Sin eventos"

```bash
curl http://localhost:3000/api/logs?limit=10
```

> En el primer arranque no hay logs: es normal. Genera eventos usando la app
> (p.ej. crea un webhook desde `/integrations`) o registra uno manualmente:
> ```bash
> curl -X POST http://localhost:3000/api/webhooks \
>   -H "Content-Type: application/json" \
>   -d '{"id":"wh1","url":"https://example.com/webhook","events":["message"]}'
> ```

---

## Performance Issues

### Página lenta
1. Corre Lighthouse contra la URL de producción (ver `PERFORMANCE.md`).
2. Busca imágenes grandes: `find public -type f -size +500k`.
3. Next.js ya minifica y hace code splitting; revisa el bundle en Vercel.

### API lenta (>500ms)
- Revisa la pestaña Network en DevTools.
- Busca el endpoint lento en `/api/logs`.
- `fetchWithRetry` reintenta automáticamente con backoff.

---

## Environment Variables

### Requeridas (producción)
```
NEXT_PUBLIC_SITE_URL=https://aura-web-chi-seven.vercel.app
API_SECRET_KEY=your_secret_here
```

### Opcional (integraciones)
```
SLACK_CLIENT_ID=xoxb-...        # enciende status de Slack
DISCORD_TOKEN=...               # enciende status de Discord
TELEGRAM_TOKEN=...              # enciende status de Telegram
TEAMS_APP_ID=...                 # enciende status de Teams
NEXT_PUBLIC_API_URL=...          # para el monitor 24/7
```

### Si no están seteadas
- `/api/webhooks` y `/api/logs` quedan públicos (inseguro en prod).
- El status de integraciones aparece como "desconectado".
- Ver `frontend/.env.example` para la plantilla completa.

---

## ¿Sigues con problemas?

1. Abre DevTools → Console (F12) en el navegador.
2. Revisa la salida de `npm run dev`.
3. Consulta `/api/logs` para eventos de error.
4. Lee `CONTRIBUTING.md` para el setup de desarrollo.
5. Abre un issue: https://github.com/raidenia3-oss/AURA-server.01/issues
