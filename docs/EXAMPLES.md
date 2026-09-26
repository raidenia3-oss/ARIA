# AURA/AME v3.0 — Real-World Examples

> Ejemplos de uso real de las integraciones y el dashboard. La autenticación
> de `/api/webhooks` y `/api/logs` usa el bearer `API_SECRET_KEY` (cuando está
> configurado). El trigger de webhooks se hace con `POST /api/webhooks` usando
> `{ "event", "data" }` (no hay sub-ruta `/trigger`).

## Example 1: Slack — reporte diario vía webhook

**Escenario:** quieres recibir un resumen diario en un canal de Slack.

### Paso 1: Registrar webhook con la URL de Slack
Usa la **incoming webhook URL** de Slack como `url`:

```bash
curl -X POST https://aura-web-chi-seven.vercel.app/api/webhooks \
  -H "Authorization: Bearer $API_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "daily-summary",
    "url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    "events": ["daily-summary"]
  }'
```

### Paso 2: Disparar el evento
```bash
curl -X POST https://aura-web-chi-seven.vercel.app/api/webhooks \
  -H "Authorization: Bearer $API_SECRET_KEY" \
  -H "Content-Type: application/json" \
  -d '{"event":"daily-summary","data":{"summary":"Reporte 2026-07-14","items":5}}'
```

El servidor hace `POST` a la URL de Slack → el mensaje aparece en el canal.

---

## Example 2: Monitorear errores desde `/api/logs`

**Escenario:** revisar errores recientes.

```bash
curl https://aura-web-chi-seven.vercel.app/api/logs?limit=10 \
  -H "Authorization: Bearer $API_SECRET_KEY" \
  | jq '.[] | select(.level=="error")'
```

El monitor 24/7 (`scripts/monitor-24-7.js`) ya hace esto cada 5 min y alerta.

---

## Example 3: Telegram — asistente personal

**Escenario:** chatear con AME desde Telegram.

```
1. Abre Telegram
2. Busca: @ame_bot
3. Click /start
4. Escribe: "¿Cómo está mi API?"
```

El bot responde con el estado (requiere `TELEGRAM_BOT_TOKEN` configurado para
encender el status en `/api/integrations/status`).

---

## Example 4: Webhook custom — GitHub

**Escenario:** recibir pushes de GitHub en AURA.

En GitHub → Settings → Webhooks, usa el Payload URL:

```
https://aura-web-chi-seven.vercel.app/api/webhooks
```

Registra previamente el webhook (con `events: ["push"]`) y luego GitHub
envía `POST /api/webhooks` con `{ "event": "push", "data": { ... } }`. AURA
lo registra en `/api/logs` y puede reenviarlo a otros webhooks suscritos.

---

## Example 5: Analytics Dashboard — métricas diarias

Visita `https://aura-web-chi-seven.vercel.app/analytics`. Métricas visibles:

- Eventos totales
- Integraciones OK (x/5)
- Webhooks activos
- Errores y su tasa
- Latencia promedio de API
- Eventos por categoría + recientes

Exportar datos crudos:

```bash
curl https://aura-web-chi-seven.vercel.app/api/logs?limit=100 \
  -H "Authorization: Bearer $API_SECRET_KEY" | jq '.' > analytics-export.json
```

---

## Example 6: Flujo multi-integración

Una acción dispara varias integraciones:

```
User Action
    ↓
Webhook recibido (POST /api/webhooks)
    ↓
Log + validación SSRF
    ↓
Reenvío a webhooks suscritos (Slack / Discord / Telegram / custom)
    ↓
Analytics actualizado
```

---

## Example 7: Recuperación de errores — retry automático

El dashboard usa `lib/fetch-retry.ts` (exponential backoff, 3 intentos).
Si un endpoint falla transitoriamente:

```
Intento 1: falla → espera 1s
Intento 2: falla → espera 2s
Intento 3: éxito ✓
```

El dashboard muestra `⚠️ error → 🔄 Reintentar`, sin bloquear la UI.
