# ARIA App — Mejoras basadas en referencias reales

## Repositorios referencia analizados

### 1. rishaadj/JARVIS (⭐ Mejor para arquitectura de agentes)
- **URL**: https://github.com/rishaadj/JARVIS
- **Stack**: Flask + SocketIO, Vosk (STT offline), Edge-TTS, multi-agente
- **Arquitectura clave**:
  ```
  AutonomousCore
      ├── PlannerAgent      — breaks goals into steps
      ├── ExecutorAgent     — runs skills
      ├── MonitorAgent      — tracks system health
      ├── EvaluatorAgent    — validates outcomes
      ├── GoalAgent         — generates autonomous goals
      ├── MemoryManager     — semantic long-term memory
      ├── VisualObserver    — passive screen awareness
      └── skills/           — 27 plug-and-play Python modules
  ```
- **Lecciones para AURA**:
  - Reemplazar el chat simple por un loop ReAct (Plan → Execute → Evaluate → Remember)
  - Agregar 27 skills modulares en `ARIA_APP/skills/`
  - Implementar screen vision con captura + análisis
  - Agregar "smart barge-in" (decir "stop" para interrumpir)

### 2. bigsk1/jarvis-voice (⭐ Mejor para producción)
- **URL**: https://github.com/bigsk1/jarvis-voice
- **Stack**: Tool RAG, MCP, memory dashboard, proactive system
- **Características clave**:
  - Tool RAG: retrieval dinámico de herramientas relevantes
  - MCP support: servidores MCP extensibles
  - Memory dashboard: UI para explorar memorias
  - Proactive API: webhooks, alertas, monitoreo
  - Dual database: cloud/local sync
  - v2.55.6 (August 2026) — production-ready
- **Lecciones para AURA**:
  - Implementar Tool RAG para discovery semántico de skills
  - Agregar MCP connector registry
  - Crear memory dashboard en el frontend
  - Sistema de proactive reminders/alerts

### 3. Karan-Negi-12/Project-Jarvis (⭐ Mejor para memoria y voz)
- **URL**: https://github.com/Karan-Negi-12/Project-Jarvis
- **Stack**: Gemini + faster-whisper + openWakeWord + ChromaDB + SpeechBrain
- **Arquitectura clave**:
  ```
  core/
      ├── llm.py              # Gemini wrapper
      ├── agent.py            # ReAct loop
      └── permissions.py      # Confirm-before-sensitive-actions
  memory/
      ├── manager.py
      ├── working_memory.py
      ├── short_term_memory.py
      └── long_term_memory.py
  voice/
      ├── stt.py              # speech → text (faster-whisper)
      ├── tts.py              # text → speech
      ├── wake_word.py        # "Hey Jarvis"
      ├── ecapa_encoder.py    # Voice biometrics
      └── speaker_id.py       # Voice verification
  tools/
      ├── base.py             # Tool registry
      ├── file_tools.py
      ├── web_tools.py
      └── system_tools.py
  ```
- **Lecciones para AURA**:
  - Implementar 3-layer memory (working/short-term/long-term)
  - Agregar wake word detection con openWakeWord
  - Speaker verification con ECAPA-TDNN
  - Tool registry con permisos

### 4. retr0-1337/jarvis (⭐ Mejor para offline/local)
- **URL**: https://github.com/retr0-1337/jarvis
- **Stack**: Whisper + Ollama + edge-tts + Docker sandbox
- **Características clave**:
  - Fully offline, no API keys
  - Agentic self-correcting loop (generate → run → test → fix → retry)
  - WebRTC VAD + Whisper confidence thresholds
  - Docker sandbox para code execution
  - Security intelligence (CVE database)
- **Lecciones para AURA**:
  - Modo offline completo con Ollama
  - Agentic self-correcting loop
  - WebRTC VAD para mejor detección de voz
  - Docker sandbox opcional para ejecución segura

### 5. deepakrakshit/jarvis (⭐ Mejor para reliability)
- **URL**: https://github.com/deepakrakshit/jarvis
- **Stack**: Gemini, pywebview, Three.js plasma UI, edge-tts
- **Arquitectura clave**:
  - Plan → Validate → Execute → Synthesizer loop
  - Reliability-first: every tool call validated before synthesis
  - Screen intelligence con Gemini Vision
  - Document intelligence pipeline
- **Lecciones para AURA**:
  - Agregar Validator step antes de ejecutar acciones
  - Screen intelligence con análisis de escritorio
  - Document Q&A pipeline

### 6. kaustav991a/J.A.R.V.I.S (⭐ Mejor para HUD React)
- **URL**: https://github.com/kaustav991a/J.A.R.V.I.S
- **Stack**: React + Vite + SCSS + GSAP + FastAPI backend
- **Características clave**:
  - Holographic HUD con React
  - Wake word (Picovoice Porcupine)
  - Streaming STT (Vosk) + batch STT (faster-whisper)
  - Acoustic echo cancellation + full-duplex
  - Piper TTS + Edge-TTS fallback
  - YOLOv8 + DeepFace vision
  - ChromaDB vector store
- **Lecciones para AURA**:
  - Migrar frontend a React + Vite para HUD más rico
  - Implementar full-duplex voice con AEC
  - Agregar YOLOv8 para object detection
  - ChromaDB para vector store

### 7. vierisid/jarvis (⭐ Mejor para arquitectura daemon)
- **URL**: https://github.com/vierisid/jarvis
- **Stack**: Go sidecar + WebSocket + React + SQLite
- **Características clave**:
  - Always-on daemon con sidecars en múltiples máquinas
  - 9 agent specialist roles
  - Visual workflow builder (n8n-style, 50+ nodes)
  - openWakeWord + Edge TTS / ElevenLabs
  - Authority gating + audit trail
- **Lecciones para AURA**:
  - Arquitectura daemon + sidecar para multi-máquina
  - Visual workflow builder para automatización
  - Authority gating para acciones sensibles

### 8. modelscope/ultron (⭐ Mejor para evolución de skills)
- **URL**: https://github.com/modelscope/ultron
- **Stack**: Memory Hub + Skill Hub + Harness Hub
- **Características clave**:
  - Memory Hub: HOT/WARM/COLD tiers, auto-summarization
  - Skill Hub: self-evolving skills, semantic clustering
  - Harness Hub: profile publishing, bidirectional sync
  - Trajectory Hub: self-training from trajectories
- **Lecciones para AURA**:
  - Implementar Memory Hub con tiers HOT/WARM/COLD
  - Skill Hub con auto-evolución
  - Profile publishing para compartir configuraciones

## Plan de mejora priorizado para ARIA App

### FASE 1: Arquitectura de agentes (2-3 días)
**Objetivo**: Transformar AURA de chatbot a sistema multi-agente

1.1. **ReAct Loop Core** (inspirado en Project-Jarvis + deepakrakshit/jarvis)
   - Plan → Validate → Execute → Synthesize
   - Validator: verificar acciones antes de ejecutar
   - Permission layer para acciones sensibles

1.2. **Tool Registry** (inspirado en rishaadj/JARVIS)
   - Sistema de 27 skills modulares
   - Skills en `ARIA_APP/skills/` como Python modules
   - Tool RAG para discovery semántico (inspirado en bigsk1/jarvis-voice)

1.3. **Memory System 3-Layer** (inspirado en Project-Jarvis)
   - Working memory (sesión actual)
   - Short-term memory (últimas N conversaciones)
   - Long-term memory (ChromaDB vector store)
   - Memoria actual JSON → migrar a SQLite + ChromaDB

### FASE 2: Voice Pipeline completo (2-3 días)
**Objetivo**: STT/TSS profesionales como los proyectos referencia

2.1. **STT offline** (inspirado en rishaadj/JARVIS + Project-Jarvis)
   - faster-whisper para batch transcription
   - Vosk para streaming STT
   - WebRTC VAD para detección de actividad
   - OpenWakeWord para wake word ("Hey AURA")

2.2. **TTS mejorado** (inspirado en todos los proyectos)
   - edge-tts como default (ya está)
   - pyttsx3 como fallback offline
   - Piper TTS como alternativa local
   - Streaming TTS para baja latencia

2.3. **Voice Biometrics** (inspirado en Project-Jarvis)
   - ECAPA-TDNN speaker verification
   - Solo responde al dueño
   - Voice enrollment one-time

### FASE 3: Screen Intelligence (1-2 días)
**Objetivo**: AURA "ve" tu pantalla como ULTRON/JARVIS

3.1. **Screen Capture** (inspirado en rishaadj/JARVIS + ULTRON)
   - pyautogui para capturas
   - Análisis pasivo cada X segundos
   - Gemini Vision para interpretar contenido

3.2. **Screen Awareness** (inspirado en deepakrakshit/jarvis)
   - Detectar errores en código
   - Sugerir soluciones proactivamente
   - OCR con pytesseract para leer texto

### FASE 4: HUD/UI mejorado (2-3 días)
**Objetivo**: Interfaz tipo Jarvis/Ultron con Three.js o React

4.1. **Opción A: React + Vite** (inspirado en kaustav991a/J.A.R.V.I.S)
   - Holographic HUD con Three.js orb
   - Real-time metrics dashboard
   - GSAP animations
   - Widget system

4.2. **Opción B: Mejorar HTML actual**
   - Glassmorphic design (inspirado en cid-moosa/jarvis-ai-assistant)
   - Canvas visualizer para voz
   - Real-time activity log
   - Dark mode con acentos cyan/purple

### FASE 5: System Control avanzado (1-2 días)
**Objetivo**: Control real del sistema como los proyectos referencia

5.1. **Desktop Control** (inspirado en todos los proyectos)
   - pyautogui + pygetwindow para mouse/teclado
   - pycaw + screen-brightness-control para volumen/brightness
   - pywinauto para control de apps Windows
   - Playwright para browser automation

5.2. **File Operations** (inspirado en Karan-Negi-12/Project-Jarvis)
   - File tools: read, write, search, organize
   - Code helper: generate, explain, debug
   - Dev agent: build complete projects

5.3. **Integrations** (inspirado en bigsk1/jarvis-voice)
   - MCP servers: DuckDuckGo, web fetch, GitHub
   - WhatsApp/Telegram bridge
   - Calendar, email, notifications

### FASE 6: Proactive & Self-Improvement (2-3 días)
**Objetivo**: AURA tome iniciativa como los proyectos avanzados

6.1. **Proactive System** (inspirado en bigsk1/jarvis-voice)
   - Event-driven alerts
   - Reminders system
   - Owner state engine (inferir foco/estado de ánimo)
   - Response quality gates (auto-regenerar respuestas malas)

6.2. **Skill Evolution** (inspirado en modelscope/ultron)
   - Skills se auto-mejoran con uso
   - Semantic clustering de skills similares
   - Skill Hub con versionado

6.3. **Compound Learning** (inspirado en ramsbaby/jarvis)
   - Mistake clusters → permanent rules
   - El mismo error no se repite
   - Behavioral metrics + insight layer

## Estructura final objetivo

```
ARIA_APP/
├── backend/
│   ├── app.py                 # FastAPI principal
│   ├── agent/
│   │   ├── core.py            # ReAct loop
│   │   ├── planner.py         # Goal decomposition
│   │   ├── executor.py        # Skill execution
│   │   ├── validator.py       # Pre-execution checks
│   │   ├── synthesizer.py     # Response synthesis
│   │   └── monitor.py         # System health
│   ├── voice/
│   │   ├── stt.py             # faster-whisper + Vosk
│   │   ├── tts.py             # edge-tts + pyttsx3 + Piper
│   │   ├── vad.py             # WebRTC VAD
│   │   ├── wake_word.py       # openWakeWord
│   │   └── speaker_id.py      # ECAPA-TDNN
│   ├── memory/
│   │   ├── working.py         # Session context
│   │   ├── short_term.py      # Recent conversations
│   │   └── long_term.py       # ChromaDB vector store
│   ├── skills/
│   │   ├── registry.py        # Skill discovery + Tool RAG
│   │   ├── system/            # System control skills
│   │   ├── web/               # Web/search skills
│   │   ├── files/             # File operations
│   │   └── custom/            # User-defined skills
│   ├── vision/
│   │   ├── screen.py          # Screen capture + analysis
│   │   ├── ocr.py             # pytesseract
│   │   └── objects.py         # YOLOv8 detection
│   ├── tools/
│   │   ├── base.py
│   │   ├── file_tools.py
│   │   ├── web_tools.py
│   │   └── system_tools.py
│   └── integrations/
│       ├── mcp.py             # MCP server manager
│       ├── whatsapp.py
│       └── telegram.py
├── frontend/
│   ├── index.html             # Current (mejorable)
│   └── react/                 # Futuro: React + Three.js HUD
├── skills/                    # 27+ skill modules
├── memory/                    # Persistent memory (JSON → SQLite)
└── requirements.txt
```

## Referencias rápidas

| Feature | Mejor referencia | URL |
|---------|-----------------|-----|
| Multi-agente core | rishaadj/JARVIS | https://github.com/rishaadj/JARVIS |
| Tool RAG + MCP | bigsk1/jarvis-voice | https://github.com/bigsk1/jarvis-voice |
| 3-layer memory | Karan-Negi-12/Project-Jarvis | https://github.com/Karan-Negi-12/Project-Jarvis |
| Offline mode | retr0-1337/jarvis | https://github.com/retr0-1337/jarvis |
| Reliability-first | deepakrakshit/jarvis | https://github.com/deepakrakshit/jarvis |
| React HUD | kaustav991a/J.A.R.V.I.S | https://github.com/kaustav991a/J.A.R.V.I.S |
| Daemon + sidecars | vierisid/jarvis | https://github.com/vierisid/jarvis |
| Skill evolution | modelscope/ultron | https://github.com/modelscope/ultron |
| Self-healing | ramsbaby/jarvis | https://github.com/ramsbaby/jarvis |

## Progreso real

### Completado
- **Fase 1** (2026-08-30): ReAct Loop Core + Tool Registry + 16 skills + Tool RAG + 3-layer memory
- **Fase 2** (2026-08-30): Voice Pipeline (faster-whisper + Vosk STT, edge-tts + Piper + pyttsx3 TTS, openWakeWord)
- **Fase 3** (2026-08-30): Screen Intelligence (capture + OCR + analyze)
- **Fase 4** (2026-08-30): HUD mejorado (glassmorphic + canvas orb)
- **Fase 5** (2026-08-30): System Control real (open apps, lock screen, list processes, volume)
- **Fase 6** (2026-08-31): Proactive System + Skill Evolution + Compound Learning

### Mejoras A (2026-08-31)
- Planificador de comandos: reconoce "abre", "bloquear", "procesos" en español
- Synthesizer: respuestas naturales ("Abriendo notepad.exe...", "Son las 16:02...")
- Import path fix: sys.path orden correcto para evitar conflictos backend antiguo

### Feature E (2026-08-31)
- Endpoint OpenAI-compatible: POST /chat/completions
- Endpoint /chat/tools: 16 skills expuestos como functions
- Endpoint /chat/models: aura-local, aura-ollama, aura-gemini, aura-groq
- Launcher nativo pywebview (app_native.py): ventana desktop sin localhost

### Integración C (2026-08-31)
- start-aura-app.ps1: script completo (Install/Start/Stop/Status)
- Desktop shortcut (ARIA OS.lnk): lanza app_native.py con doble clic
- ARIA_APP/backend/api/compat.py: OpenAI-compatible API router

### Pendiente
- B) Producción: empaquetar como .exe con PyInstaller
- F) Distro Linux: USB/Arch + Hyprland
- Descargar modelos Vosk y openWakeWord para STT/wake word offline
- Migrar frontend a React + Vite
