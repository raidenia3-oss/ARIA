# AURA OS — Guía de Operaciones Soberanas y Runbook Local

> **BLOQUE 39 — End-to-End Verification & Sovereign Operations Guide**
> Todo el ecosistema AURA OS opera 100% local-first: sin servicios en la nube, sin fugas de datos, sin tokens en texto plano.

---

## 1. Arquitectura Soberana

| Componente | Punto de entrada | Estado |
|---|---|---|
| Host PC FastAPI | `backend/main.py` (uvicorn :8000) | ✅ Consolidado |
| Jan (motor local) | `http://localhost:1337` | ✅ Opcional |
| mDNS Anunciador | `backend/mobile/discovery.py` (_aura-host._tcp.local) | ✅ Consolidado |
| Pasarela WebSocket | `backend/websocket_manager.py` | ✅ Consolidado |
| Bóveda Cifrado (at-rest) | `backend/security/crypto.py` (Fernet AES-256) | ✅ Consolidado |
| Whisper STT local | `backend/audio/transcriber.py` | ✅ Consolidado |
| Master Launcher | `scripts/aura-master.py` | ✅ Consolidado |
| Discord Bot (Ruby) | `services/discord-bot/bot.rb` | ✅ Consolidado |
| Cliente Móvil AME | `frontend/app/ame/page.tsx` | ✅ Consolidado |

---

## 2. Comandos de Encendido

### 2.1 Un solo comando (recomendado)
```powershell
python scripts/aura-master.py
```
Arranca backend + Discord (Ruby) en paralelo, espera a que el backend responda `/health`, ejecuta el health-check aggregator y queda a la espera de `Ctrl+C` para apagado limpio.

### 2.2 Solo backend (sin Discord)
```powershell
python scripts/aura-master.py --no-discord
```

### 2.3 Health-check (sin levantar)
```powershell
python scripts/aura-master.py --check
```
Retorna JSON con `overall` (`ok`/`degraded`) y checks de backend, Jan y Discord.

### 2.4 Manual
```powershell
# Backend
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Discord (Ruby)
ruby services/discord-bot/bot.rb

# Frontend (Next.js)
cd frontend && npm run dev
```

---

## 3. Comandos de Mantenimiento

### 3.1 Validación rápida (AGENTS.md)
```powershell
curl.exe -s http://localhost:8000/health
curl.exe -s http://localhost:8000/api/system/status
curl.exe -s http://localhost:8000/chat/tools | ConvertFrom-Json | Measure-Object
```

### 3.2 Typecheck frontend
```powershell
cd frontend && npm run typecheck
```

### 3.3 Tests de integración (backend vivo)
```powershell
.venv\Scripts\python.exe -m pytest tests/test_story_memory.py tests/test_e2e_backend.py tests/test_audio_transcribe.py tests/test_audio_transcriber.py tests/test_aura_master.py tests/test_aura_master_launcher.py tests/test_vault_crypto.py tests/test_local_crypto.py tests/test_ame_sync.py tests/test_mdns_discovery.py tests/test_agent_scheduler.py -q --tb=line
```

### 3.4 Auditoría de limpieza
```powershell
git diff --check
```

---

## 4. Recuperación ante Fallos

| Fallo | Acción |
|---|---|
| Backend no responde | `python scripts/aura-master.py --check` → si `degraded`, reinicia con `aura-master.py` |
| Discord no arranca | `--no-discord` omite el bot (el canon feed cae al backend) |
| Puerto 8000 ocupado | `python scripts/aura-master.py --port <n>` |
| Whisper STT 503 | `AURA_WHISPER_ENGINE=stub` para tests/demo; en prod instala `faster-whisper` + `torch` |
| Bóveda bloqueada | `POST /api/vault/unlock` con el secreto maestro correcto |
| mDNS no descubre | `AURA_HOST_IPS=127.0.0.1` como fallback manual |

---

## 5. Contratos de Seguridad

- **Nunca** se envía audio a la nube: el STT procesa localmente (Faster-Whisper o stub).
- **Nunca** se exponen tokens: la API key (`X-API-Key`) solo se valida si `AURA_API_KEY` está definida en `.env` (no en `.env.local`).
- **Nunca** se persiste el secreto maestro: la clave Fernet vive solo en memoria (CryptoKey no extraíble) mientras la sesión está abierta.
- **Nunca** se hace commit de `.env.local` (gitignore implícito).

---

## 6. Estado de Validación (BLOQUE 39)

- `pytest` (11 archivos, backend vivo): **100% pasan**
- `npx tsc --noEmit`: **0 errors**
- `git diff --check`: **limpio**

---

## 7. Referencia Rápida de Comandos

```powershell
# Encendido unificado
python scripts/aura-master.py                     # todo el ecosistema
python scripts/aura-master.py --no-discord        # solo backend
python scripts/aura-master.py --check             # health-check JSON

# Apagado limpio (graceful shutdown sin huérfanos)
# Ctrl+C en la terminal del aura-master.py

# Validación completa del ecosistema
.venv\Scripts\python.exe -m pytest tests/ -v --tb=line
cd frontend; npm run typecheck; cd ..
git diff --check

# Endpoints clave
curl.exe -s http://localhost:8000/health
curl.exe -s http://localhost:8000/api/audio/transcribe/status
curl.exe -s http://localhost:8000/api/mobile/discovery
curl.exe -s http://localhost:8000/api/story/works
```

---

*Documento cerrado en BLOQUE 39 — ecosistema AURA OS soberano, local-first, validado end-to-end.*