# AURA Neural Bridge

## Acceso rápido

- Importar: `from AURA_Core.neural.router import neural_bridge`
- Uso básico: `task_id = await neural_bridge.ask("Prompt", censorship=False)`
- Estado: `state = await neural_bridge.get_status(task_id)`

## Archivos

- `router.py`: enrutador multi-modelo y cola asíncrona.
- `knowledge_base.py`: sistema de “gems” para inyección de contexto.
- `queue_state.json`: persistencia de tareas.
- `neural_status.json`: estado visual para el HUD.

## Notas

- El modo cloud está preparado pero requiere configuración segura de API keys.
- `execute_autonomous_task` implementa planificación, generación, validación y autodepuración.
