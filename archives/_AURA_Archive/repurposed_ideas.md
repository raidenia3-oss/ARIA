# Repurposed Ideas - AURA Archive Analysis

## router.py (Cognitive Routing for Ollama)
**✅ ALREADY INTEGRATED** → Migrated to `AURA_Core/ai_router.py`
- `detect_task_type()` → keyword-based routing logic usable in Fase 5
- `get_best_model()` → selection logic for AuraCognitiveRouter
- `call_ollama_smart()` → Ollama local API caller (reusable for offline mode)
- `get_model_for_consciousness()` → consciousness-to-model mapping (future "multi-consciousness" feature)

## personality.py
**📌 SANDBOX CANDIDATE** → Personality profiles for future AURA instances
- Contains tone/persona definitions that could power customizable agent personalities

## models.py
**📌 SANDBOX CANDIDATE** → Model registry definitions
- Could be merged into TOOL_REGISTRY in skills_forge.py for model-aware tool execution

## lmstudios.py
**📌 SANDBOX CANDIDATE** → LM Studio local inference integration
- Useful for offline fallback when cloud APIs are unavailable

## local_bridge.py / aura_bridge.py
**📌 SANDBOX CANDIDATE** → Local↔cloud bridging logic
- Could be reused when implementing the Vercel↔Railway bridge in Fase 5

## youtube_learner.py
**📌 SANDBOX CANDIDATE** → Web scraping / content learning module
- Could feed into the memory manager for context augmentation

## fix.py / hacker.py / hermes_server.py
**❌ DEPRECATED** → Old utility scripts from early prototypes
- Not reusable in current architecture