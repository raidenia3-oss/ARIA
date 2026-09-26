# Base Literaria AURA/AME — Frontend

Interfaz en `/story` (Next.js App Router) para gestionar la base literaria.
Solo consume el contrato real `backend/story_routes.py` (`/api/story/*`).

## Arquitectura

- `lib/story-types.ts` — tipos que reflejan los modelos reales de `backend/story_memory/`.
- `lib/story-client.ts` — cliente tipado; llama al proxy local, nunca al backend directamente.
- `app/api/story/[...path]/route.ts` — proxy server-side hacia `${BACKEND_URL}/api/story/*`.
  El backend y cualquier credencial quedan fuera del cliente; no se envían tokens.
- `lib/story-format.js` — utilidades puras (orden cronológico, etiquetas de estado, parsing).
- `components/story/*` — selector de obra, CRUD de personajes, canon/cronología,
  planificador de capítulos, panel de coherencia y vinculación de sesión.

## Integración con el chat (sin romper contratos)

- **`/chat`**: `StorySessionLink` guarda el `session_id` en
  `localStorage["aura-chat-session-id"]`; el chat lo añade como campo
  **opcional** del FormData y `app/api/ame-core/route.ts` lo reenvía a
  `/api/chat`, que ya aceptaba `session_id` opcional.
- **`/ame/[ameId]`**: el chat ya envía `session_id = ameId` a través de
  `/api/mobile/chat` (sin cambios). `ChatIntegration` vincula ese `ameId`
  a obra+personaje vía `/api/story/sessions/{ameId}/context`, de modo que
  el backend inyecta el contexto literario sin alterar el payload del chat.
- Si no hay sesión vinculada, los chats funcionan exactamente igual que antes.

## Estados de UI

Cada panel maneja carga, vacío, error (con `detail` del backend) y confirmación
de guardado. Ningún componente muestra ni almacena tokens.

## Pruebas

- `tests/story-format.test.mjs` — utilidades puras (`node --test`).
- Backend: `pytest tests/test_story_memory.py` (sin modificaciones).

## Chrome

**NO VALIDADO MANUALMENTE — requiere Chrome y sesión interactiva.**
