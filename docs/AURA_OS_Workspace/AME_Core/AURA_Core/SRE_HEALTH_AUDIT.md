# AURA SRE Health Audit

Fecha: 2025-06-16

## Hallazgos por dominio

### 1. Resiliencia LLM / routers

- `AURA_Core/ai_router.py`: riesgo de crash si proveedor retorna body vacío, JSON malformado o timeout sin reintento.
- `AURA_Core/local_llm_router.py`: idem; no existe fallback automático a Ollama local ni backoff.
- `AURA_Core/neural/router.py`: ya mejorado, pero mantiene un solo reintento implícito y sin métricas.
- `plugins/ai_router.py`: posible acoplamiento circular con `AME_Core/proxy_manager.py` a revisar.

### 2. Conectividad y bloqueos

- `AME_Core/ws_server.py`: si un cliente cierra el socket abruptamente, el `writer.drain()` puede bloquear el event loop si no se maneja `CancelledError` / `ConnectionResetError`.
- `AURA_Core/godot_bridge.py` y `godot_game/autoloads/AURABridge.gd`: riesgo de deadlock si se serializa JSON gigante por WebSocket sin chunking ni backpressure.
- Varios scripts terminan en `.bat` con `python ...` pero sin captura de `ERRORLEVEL` ni logs.

### 3. Carga CPU y telemetría

- `AURA_Core/rollercoin/` y tareas en segundo plano existe riesgo de latencia por polling agresivo.
- `AURA_Core/monitors/world_monitor.py` actualizado: OK (sleep 5s).

### 4. Estructura / datos

- Falta un estado central de agentes (`agent_status.json`).
- `AURA_HUD` no existe como carpeta unificada (UI repartida entre `AME_Core/templates`, `AME_Core/static/js`, etc.).

## Plan de parcheo priorizado

1. Añadir validador + fallback en `AURA_Core/ai_router.py` y `AURA_Core/local_llm_router.py`.
2. Hardened reconnect + timeouts en `AME_Core/ws_server.py`.
3. Estructura base `AURA_HUD/`.
4. Estado central `AURA_Core/data/agent_status.json`.
