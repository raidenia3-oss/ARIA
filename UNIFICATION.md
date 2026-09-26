# AURA OS v4.0 — Unificación AURA_APP + ARIA_v4
# Fecha: 2026-09-20

## Estructura Unificada

### AURA_APP/ (base principal)
- `aria_main.py` — Entry point desktop standalone (IPC pipes, sin HTTP)
- `aria_startup.py` — Arranque autónomo (sin input(), wake word)
- `aria_logic_engine.py` — LogicEngine IPC (stdin/stdout)
- `backend/aria_adaptive_engine.py` — Adaptive engine con auto-learning
- `backend/autonomy/` — Módulos de autonomía:
  - `autonomous_core.py` — 5 loops background (SCAN, PREDICT, HEALTH, PATTERN, ERROR)
  - `voice_activation.py` — Wake word detection
  - `self_healer.py` — Auto-recuperación ante errores
  - `context_predictor.py` — Predicción contextual proactiva
  - `proactive_scheduler.py` — Programación inteligente basada en patrones
- `backend/learning/` — Sistema de aprendizaje:
  - `compound.py` — Compound learning (errores → reglas permanentes)
- `backend/memory/` — Sistema de memoria:
  - `working.py` — Working memory (session-scoped)
  - `short_term.py` — Short-term memory (file-backed)
  - `long_term.py` — Long-term memory (persistent facts)
- `backend/usb_intelligence.py` — Detección + expansión USB
- `backend/skills/` — 25 skills + 10 tools
- `backend/automation/scheduler.py` — Scheduler cron completo
- `backend/voice/pipeline.py` — STT/TTS pipeline
- `backend/observability/` — Metrics y health checks
- `backend/resilience/` — Retry, circuit breaker, fallback
- `frontend/index.html` — HUD glassmorphic
- `data/` — user_profile.json, context_patterns.json, proactive_tasks.json, error_log.json

### ARIA_v4/AURA_APP/ (complementos)
- `backend/logic/` — Wrappers para LogicEngine y AdaptiveEngine
- `backend/intelligence/aria_brain/` — Brain components (reasoning, decision, emotion)
- `backend/learning/` — Incluye compound.py + behavior_analyzer + adaptive_learner
- `backend/memory/` — Copia de AURA_APP memory modules
- `backend/api/` — FastAPI backend con routes
- `backend/storage/` — Storage abstractions
- `backend/config/` — Config models

## Mapeo de Unificación

| Módulo | Ubicación | Origen |
|--------|-----------|--------|
| LogicEngine | `AURA_APP/aria_logic_engine.py` + `AURA_APP/backend/logic/aria_logic_engine.py` (wrapper) | AURA_APP original |
| AriaAdaptiveEngine | `AURA_APP/backend/aria_adaptive_engine.py` + `AURA_APP/backend/logic/aria_adaptive_engine.py` (wrapper) | AURA_APP original |
| AutonomousCore | `AURA_APP/backend/autonomy/autonomous_core.py` | ARIA_v4 → AURA_APP |
| VoiceActivation | `AURA_APP/backend/autonomy/voice_activation.py` | Ambos (unificado) |
| SelfHealer | `AURA_APP/backend/autonomy/self_healer.py` | Ambos (unificado) |
| ContextPredictor | `AURA_APP/backend/autonomy/context_predictor.py` | Ambos (unificado) |
| ProactiveScheduler | `AURA_APP/backend/autonomy/proactive_scheduler.py` | Ambos (unificado) |
| CompoundLearning | `AURA_APP/backend/learning/compound.py` + `ARIA_v4/AURA_APP/backend/learning/compound.py` | AURA_APP → ARIA_v4 |
| WorkingMemory | `AURA_APP/backend/memory/working.py` + `ARIA_v4/AURA_APP/backend/memory/working.py` | AURA_APP → ARIA_v4 |
| ShortTermMemory | `AURA_APP/backend/memory/short_term.py` + `ARIA_v4/AURA_APP/backend/memory/short_term.py` | AURA_APP → ARIA_v4 |
| LongTermMemory | `AURA_APP/backend/memory/long_term.py` + `ARIA_v4/AURA_APP/backend/memory/long_term.py` | AURA_APP → ARIA_v4 |
| USBIntelligence | `AURA_APP/backend/usb_intelligence.py` | AURA_APP original |
| SkillRegistry | `AURA_APP/backend/skills/registry.py` | AURA_APP original |
| AutomationScheduler | `AURA_APP/backend/automation/scheduler.py` | AURA_APP original |
| VoicePipeline | `AURA_APP/backend/voice/pipeline.py` | AURA_APP original |

## Features Activadas
1. ✅ Arranque autónomo (sin input())
2. ✅ 5 loops de background (autonomous_core)
3. ✅ Wake word detection (voice_activation)
4. ✅ Auto-recuperación (self_healer)
5. ✅ Predicción contextual (context_predictor)
6. ✅ Programación proactiva (proactive_scheduler)
7. ✅ Compound learning (compound.py)
8. ✅ Sistema de memoria (working + short_term + long_term)
9. ✅ Detección USB + expansión
10. ✅ IPC pipes (sin HTTP/servers)
11. ✅ Skills registry (25 skills)
12. ✅ Automation scheduler (cron)

## Ejecución
```powershell
# Standalone desktop
.venv\Scripts\python.exe AURA_APP\aria_main.py

# O arranque autónomo directo
.venv\Scripts\python.exe AURA_APP\aria_startup.py
```
