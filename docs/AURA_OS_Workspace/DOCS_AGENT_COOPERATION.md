# Protocolo de Cooperación Cruzada de Agentes

Reglas y formato para que **Cline** y **Grok** colaboren en la resolución de problemas del repositorio AURA/AME.

## 1. Formato de reporte de error

- Cline registra la señal de error en:
    - `ame-backend/bridge_state/state.json` (campo `logs` y `pending`)
    - o `AME_Core/logs/agent_errors.log` si existe
- Cada evento debe incluir:
    - `ts`: timestamp UTC (ISO8601)
    - `source`: módulo o script donde se originó
    - `action`: nombre corto de la operación
    - `requires_assist`: true cuando no puede resolverse de forma autónoma
    - `error_dump`: stack trace, código de estado, contexto útil

## 2. Flujo cooperativo

1. **Cline** detecta un error no recuperable.
2. **Cline** escribe el evento con `requires_assist: true` en el endpoint `/api/bridge/update`.
3. **Grok** consulta el estado del sistema con `GET /api/bridge/status`.
4. **Grok** diagnostica y entrega una solución basada en:
    - Estado actual (`pending_tasks`, `recent_logs`)
    - Variables de entorno expuestas en `env`
5. **Cline** aplica la corrección indicada por Grok y documenta el resultado con un nuevo evento `POST /api/bridge/update`.

## 3. Convenciones

- Usar solo rutas relativas al repositorio.
- Evitar enumeración de archivos en cada mensaje; usar `list_files` solo cuando sea estrictamente necesario.
- Reutilizar módulos existentes (`AME_Core`, `Shadow-Core`, `ame-backend`).
- Actualizar siempre `task_progress` tras completar cada paso.
