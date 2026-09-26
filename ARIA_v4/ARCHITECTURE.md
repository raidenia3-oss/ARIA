# ARIA OS v4.0 — Architecture

## Overview

ARIA OS v4.0 es un asistente virtual inteligente con arquitectura AI-driven. No usa scripts tradicionales — toma decisiones basadas en IA adaptativa.

## Architecture Layers

```
┌─────────────────────────────────────────────────┐
│                   UI Layer                       │
│  DesktopUI (PyQt5) │ OrbVisual │ TrayIcon      │
├─────────────────────────────────────────────────┤
│                 IPC Layer                        │
│  IPCServer │ IPCClient (named pipes)            │
├─────────────────────────────────────────────────┤
│               Backend Logic                      │
│  LogicEngine │ AriaAdaptiveEngine               │
│  IntentDetector │ PStackOrchestrator            │
├─────────────────────────────────────────────────┤
│              Intelligence                        │
│  AriaBrain (8 submódulos) │ SkillExecutor       │
│  ToolRegistry (20+ tools)                       │
├─────────────────────────────────────────────────┤
│           Integration (5 OSS Repos)              │
│  Headroom │ Claude Context │ Agent-skills       │
│  Agency-agents │ Skill Recorder                  │
├─────────────────────────────────────────────────┤
│             Expansion                            │
│  USB Intelligence │ Model Loader │ Cache Manager│
├─────────────────────────────────────────────────┤
│          Execution & Storage                     │
│  STT │ LLM │ TTS │ SQLite │ Profile │ Skills   │
├─────────────────────────────────────────────────┤
│               API Layer (FastAPI)                │
│  Routes: chat, usb, learning, system, pstack    │
└─────────────────────────────────────────────────┘
```

## Key Components

### AriaBrain (`backend/intelligence/aria_brain/`)
- MemoriaManager — Gestión de memoria semántica
- ReasoningEngine — Análisis y razonamiento
- DecisionMaker — Toma de decisiones
- LearningSystem — Aprendizaje continuo
- CreativityEngine — Generación creativa
- EmotionSimulator — Simulación emocional
- PredictionModel — Predicción de acciones
- ExplanationGenerator — Explicación de decisiones

### PStack Orchestrator
Orquestador de flujos con auto-detection:
- `/potato-mode` — Auto-detecta qué necesitas
- `/blast-radius` — Valida impacto de cambios
- `execute_workflow` — Ejecuta workflows completos

### USB Intelligence
Detección automática de USBs con expansión:
- Modelos `.gguf`, `.bin`
- Datos `.jsonl`, `.json`, `.csv`
- Cache y backups

## AI-Driven Flow

```
Usuario → IntentDetector → AriaAdaptiveEngine → PStack → SkillExecutor
                    ↓                         ↓
              LearningHistory          Profile Update
                    ↓                         ↓
             MemoryManager         Auto-Adaptation
```

## Data Flow

```
User Input → Intent (IA) → PStack Workflow → Skill Execution
                                            ↓
                                    AriaBrain (if needed)
                                            ↓
                                    Memory + Learning
                                            ↓
                                    Profile + Adaptation
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/aria/chat | POST | Chat principal |
| /api/aria/usb/status | GET | Estado USB |
| /api/aria/usb/expand | POST | Expandir con USB |
| /api/aria/auto | POST | ARIA automática |
| /api/aria/pstack/potato-mode | POST | Auto-detect workflow |
| /api/aria/pstack/blast-radius | GET | Impact analysis |
| /api/system/health | GET | Health check |

## Version

v4.0.0 — AI-Driven, No Scripts, Adaptive Learning
