# AME WebSocket Bridge

## Estructura

- `ame-backend/src/api/ws_bridge.py` — endpoint `/ws/bridge` con JWT y watchdog.
- `ame-backend/src/api/auth_jwt.py` — helper de creación/validación de JWT.
- `ame-backend/src/api/n8n_ws_bridge.py` — base de bridge y helper de reconnect.
- `ame-backend/web_pages/ame_explorer/index.html` — dashboard conectado al bridge.
