# Advanced Contributing Guide — AURA/AME v3.0

> Guía extendida para la Fase 58 (React Native / Fine-tuning / Analytics).
> La app web v3.0 ya está completa y verificada; esto es lo que Cline necesita
> para las piezas de backend/móvil que requieren servicios externos y
> toolchains nativas.

## For Cline (Phase 58)

### Antes de empezar

1. Lee `README.md`
2. Lee `CONTRIBUTING.md`
3. Lee `setup-phase-58.md`
4. Corre `npm run dev` y verifica que v3.0 funciona localmente

### Fase 58: guías por opción

#### Opción A: React Native Mobile App

**Estructura:**
```
ame-mobile/
├─ app/
│  ├─ (auth)/        # pantallas de auth
│  ├─ (app)/         # pantallas principales
│  └─ api/           # cliente API
├─ lib/
│  ├─ hooks.ts       # React hooks
│  ├─ store.ts       # estado (Zustand)
│  └─ firebase.ts    # config Firebase
└─ package.json
```

**Requisitos:** Expo 48+, Firebase para auth + sync, Zustand para estado,
AsyncStorage para offline, TypeScript strict, tests en rutas críticas.

**Antes de PR:**
```bash
npm run typecheck
npm run lint
npm test
expo start   # probar en dispositivo/simulador
```

#### Opción D: Fine-tuning + Multimodal

**Pipeline:**
```
1. Recolección    (scripts/collect-training-data.py) → training-data.jsonl
2. Fine-tuning     (scripts/finetune-model.py)        → ./fine-tuned-ame/
3. Endpoints API   (/api/ai/multimodal)               → texto + imagen + audio
```

**Requisitos:** Python 3.10+, GPU recomendada, credenciales HuggingFace,
logging y error handling completos.

**Antes de PR:**
```bash
python -m pytest tests/
python scripts/finetune-model.py --test   # dry run
curl -X POST http://localhost:3000/api/ai/multimodal -d '{"text":"test"}'
```

#### Opción F: Analytics Engine + ML

**Componentes:**
```
1. Agregación    (scripts/analytics-engine.py)  → corre por hora
2. ML            (Prophet forecast, Isolation Forest anomalías)
3. API           (/api/analytics)               → métricas + forecast + anomalías
```

**Requisitos:** PostgreSQL o SQLite, Redis para cache, pandas + scikit-learn,
scheduled jobs (EasyCron/Vercel Cron), monitoreo.

---

## Code Standards

### TypeScript
```typescript
// ✅ HACER
const fetchData = async (id: string): Promise<Data> => {
  const response = await fetchWithRetry(`/api/data/${id}`);
  if (!response.ok) throw new Error("Failed to fetch");
  return response.json();
};

// ❌ NO
const fetchData = async (id) => {
  return fetch(`/api/data/${id}`).then((r) => r.json());
};
```

### Error Handling
```typescript
// ✅ HACER
try {
  const result = await riskyOperation();
  return { success: true, data: result };
} catch (error) {
  logger.error("Operation failed", { error, context });
  return { success: false, error: (error as Error).message };
}

// ❌ NO
const result = await riskyOperation(); // sin manejo
return result;
```

### Logging
```typescript
// ✅ HACER
logger.info("User created", { userId: id, email });
logger.error("Database error", { error: e, query });

// ❌ NO
console.log("User created"); // no queda registrado en /api/logs
```
> El proyecto ya centraliza logs en `lib/logger.js` (expuestos en `/api/logs`).

---

## Testing (local)

```bash
npm run typecheck   # tsc -p tsconfig.local.json --noEmit
npm run lint:local  # eslint -c eslint.local.mjs .
npm test            # node --test tests/*.mjs
```

> Nota: `npm run lint` (eslint-config-next) falla en este entorno porque el
> `next` local es una versión antigua; usa `npm run lint:local`.

---

## PR Checklist

Antes de abrir un PR:

- [ ] `npm run typecheck` → 0 errores
- [ ] `npm run lint:local` → 0 errores
- [ ] `npm test` → pass
- [ ] Tests nuevos para features nuevas
- [ ] Documentación actualizada (README, etc.)
- [ ] Sin `console.log` en código de producción
- [ ] Sin secrets hardcodeados
- [ ] Mensajes de commit claros
- [ ] Branch actualizada con `main`

---

## Deployment

### Vercel (web)
```bash
git push origin feature-branch
# preview URL → revisar → PR → merge a main → deploy prod
```

### Scripts Python (Fase 58)
Desplegar en cloud (AWS Lambda / Cloud Functions) o usar EasyCron para
agendar `analytics-engine.py` / `finetune-model.py`.

---

## Ayuda

- Issues: GitHub Issues
- Docs: `README.md`, `CONTRIBUTING.md`, `setup-phase-58.md`, `TROUBLESHOOTING.md`
