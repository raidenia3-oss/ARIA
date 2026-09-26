# DIAGNÓSTICO EN CALIENTE — AURA Core

## 1) Resumen ultracorto

- Concepto 1 (Prompt denso Kimi K-2.7 Code / GLM 5.2): **VIABLE AHORA**.
    - Existe `AURA_Core/automation/llm_router.py` con endpoint primario HF Space + fallback LM Studio.
    - Existe `AURA_Core/ai_router.py` y `AURA_Core/neural/cloud_router.py` para enrutar por tarea.
    - Añadir cabeceras/parametrización por proveedor es trivial (no requiere infraestructura nueva).
- Concepto 2 (Local Edge absoluto, eliminar cloud fallbacks): **VIABLE CON CAMBIO DE CONFIG**.
    - LM Studio ya está configurado como endpoint secundario (`http://localhost:1234/v1`).
    - Para forzar “solo local”, hay que modificar la selección de endpoint para no usar HF Space cuando LM Studio esté healthy.
- Concepto 3 (CLI Agent wrapper autónomo sin UI): **VIABLE Y NUEVO**.
    - No existe wrapper dedicado en `AURA_Core/tools/`; se puede crear sin tocar WebSockets ni KnowledgeGraph.

## 2) Hallazgos clave (evidencia)

- `AURA_Core/automation/llm_router.py:64-84`: configura endpoints `primary` (HF Space) y `secondary` (LM Studio).
- `AURA_Core/automation/llm_router.py:92-130`: método `chat()` con failover.
- `AURA_Core/ai_router.py`: enrutamiento por tarea (code/vision/fast_vision).
- `AURA_Core/memory/knowledge_graph.py`: KnowledgeGraph ya aislado (sin importar router).

## 3) Modificaciones que se aplican a continuación

- Refactor de enrutador (compatibilidad mejorada + modo local preferente).
- Nuevo módulo CLI Agent wrapper para llamadas directas desde terminal Windows.

## 4) Impacto

- No se alteran WebSockets existentes.
- No se altera la firma pública de `llm_router.chat(...)`.
- KnowledgeGraph no se toca.

## 5) Siguiente paso

- Se añade el módulo de router extendido + el wrapper CLI.
