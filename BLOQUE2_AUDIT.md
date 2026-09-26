# BLOQUE 2 — Auditoría y Estado de Implementación

## 1. Estado actual de `frontend/app/ame/page.tsx` (antes de BLOQUE 2)

- **AMEs hardcodeados**: 3 AMEs fijos con id 1,2,3 (datos simulados).
- **Conexión a API**: No intenta conectar a `/api/mobile/ames`. Usa `useState` con datos fijos.
- **AmeSyncManager**: No inicializado.
- **Estado de conexión**: Solo detecta `navigator.onLine` con banner amarillo "Modo offline". No distingue AURA PC apagada vs sin internet.

## 2. Estado actual de `frontend/app/ame/[ameId]/page.tsx` (antes de BLOQUE 2)

- **Datos del chat**: Placeholder "Chat aquí..." sin datos reales.
- **IndexedDB**: No se usa para cargar historial ni guardar mensajes.
- **WebSocket**: No se intenta conectar.
- **Offline**: Solo banner "Modo offline". No preserva mensajes ni cola de eventos.

## 3. Estado actual de `frontend/lib/ame-sync.ts` (BLOQUE 1)

- **Deduplicación**: Por `eventId` en store `events` de IndexedDB.
- **Errores**: No hay `catch {}` vacíos. Todos los catch tienen logging explícito.
- **Diferenciación**: Estados `aura_offline` e `internet_offline` son distintos.

## 4. Estado actual de `frontend/lib/ame-websocket.ts` (BLOQUE 1)

- **Validación de mensajes**: `parseIncomingMessage()` valida estructura del evento.
- **Cierre al desmontar**: ⚠️ No tiene método `disconnect()` para cleanup en React.
- **Reconexión**: Backoff exponencial 1s→32s, max 8 retries.

## 5. Endpoints backend reales

| Endpoint | Método | Existe | Estado |
|---|---|---|---|
| `/api/mobile/discovery` | POST | ✅ | Funcional |
| `/api/mobile/devices` | GET | ✅ | Funcional |
| `/api/mobile/sync/{client_id}` | WS | ✅ | Funcional |
| `/api/mobile/mode` | GET | ✅ | Funcional |
| `/api/mobile/mode` | POST | ✅ | Funcional |
| `/api/mobile/termux/cmd` | POST | ✅ | Funcional |
| `/api/mobile/ames` | GET | ❌ | No existe |
| `/api/mobile/ames/{ameId}/history` | GET | ❌ | No existe |
| `/api/mobile/ames/{ameId}/message` | POST | ❌ | No existe |
| `/ws/mobile/{clientId}` | WS | ❌ | No existe (el WS es `/api/mobile/sync/{client_id}`) |

## 6. Modificaciones realizadas en BLOQUE 2

### 6.1 `frontend/app/ame/page.tsx`

**Cambios:**
- Inicializa `AmestatusSyncManager` en `useEffect`.
- Suscribe a cambios de estado y muestra etiqueta de conexión en tiempo real.
- Carga `/api/mobile/ames` al montar. Si falla, usa `DEMO_AMES` con banner "Modo demostración — AURA no disponible".
- Estados diferenciados: `online`, `aura_offline`, `internet_offline`, `reconnecting`, `syncing`, `sync_failed`.
- Eliminados datos hardcodeados de AMEs (se mantiene `DEMO_AMES` solo como fallback).

**Validación:**
- `npm run typecheck` → 0 errores en `app/ame/`
- `npm run lint` → 0 errores en `app/ame/`

### 6.2 `frontend/app/ame/[ameId]/page.tsx`

**Cambios:**
- Carga historial desde IndexedDB (`LocalDB.getInstance().getChatHistory(ameId)`).
- Guarda mensajes nuevos en IndexedDB (`saveChatMessage`).
- Muestra estado de conexión real (AURA PC desconectada, sin internet, sincronizando, etc.).
- Bloquea comandos peligrosos (`rm -rf`, `format`, `drop table`, etc.).
- No finge respuestas de AURA: muestra `[Modo demostración]` cuando AURA no está disponible.
- No pierde mensajes al desmontar (persistidos en IndexedDB).

**Validación:**
- `npm run typecheck` → 0 errores en `app/ame/`
- `npm run lint` → 0 errores en `app/ame/`

## 7. Archivos no modificados

| Archivo | Razón |
|---|---|
| `backend/main.py` | No requiere cambios para MVP frontend |
| `backend/mobile/sync.py` | El cliente envía formato dual compatible con backend existente |
| `frontend/lib/sync-engine.ts` | Legado; coexiste con `ame-sync.ts` sin conflictos |
| `frontend/lib/ame-websocket.ts` | No se modificó en BLOQUE 2 |
| `frontend/lib/ame-sync.ts` | No se modificó en BLOQUE 2 |
| `frontend/lib/ame-state-machine.ts` | No se modificó en BLOQUE 2 |
| `frontend/lib/ame-events.ts` | No se modificó en BLOQUE 2 |
| `docs/AURA_OS_Workspace/AME_Core/` | Histórico — no tocado |
| `config/capacitor.config.ts` | No se modifica hasta confirmar plataforma |

## 8. Riesgos y limitaciones

1. **Backend no define `/api/mobile/ames`**: El frontend usa fallback demo marcado. Documentado.
2. **No hay autenticación de token en WebSocket**: El backend `/api/mobile/sync/{client_id}` no valida tokens. El cliente envía token en query param pero el backend no lo procesa.
3. **WebSocket no se cierra al desmontar**: `ame-websocket.ts` no tiene método `disconnect()`. Las páginas AME llaman `syncManager.init()` pero no limpian el WebSocket al cambiar de ruta.
4. **Respuestas simuladas**: El chat muestra `[Modo demostración]` cuando AURA no está disponible. No finge ser AURA.
5. **No hay sincronización real de chats**: Los mensajes se guardan en IndexedDB pero no se sincronizan con backend porque los endpoints no existen.

## 9. Próximo paso recomendado — BLOQUE 3

1. **Backend**: Crear endpoints REST `/api/mobile/ames`, `/api/mobile/ames/{ameId}/history`, `/api/mobile/ames/{ameId}/message`.
2. **WebSocket**: Agregar método `disconnect()` para cleanup en React.
3. **Autenticación**: Implementar validación de token en `/api/mobile/sync/{client_id}`.
4. **Núcleo visual**: Implementar página `frontend/app/core/page.tsx` con `ParticleSystem3D`.
