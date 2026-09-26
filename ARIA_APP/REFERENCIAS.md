# ARIA App — Referencias base

## Proyectos referencia (analizados 2026-08-30)

### Multi-agente y arquitectura
- **rishaadj/JARVIS** — Flask+SocketIO, Vosk STT offline, Edge-TTS, 27 skills, screen vision, Planner/Executor/Monitor/Evaluator/Goal agents, self-evolving skill synthesis
  - URL: https://github.com/rishaadj/JARVIS
- **modelscope/ultron** — Self-evolving collective intelligence, Memory Hub (HOT/WARM/COLD), Skill Hub, Harness Hub, Trajectory Hub para self-training
  - URL: https://github.com/modelscope/ultron
- **ramsbaby/jarvis** — Discord bot + RAG + Insight Layer, 256 automation scripts, self-healing, compound learning, proactive owner state engine
  - URL: https://github.com/ramsbaby/jarvis

### Producción y memoria
- **bigsk1/jarvis-voice** — v2.55.6 (Aug 2026), Tool RAG, MCP support, memory dashboard, proactive API/reminders, dual database cloud/local, OpenCode integration, monitoring stack Grafana+Prometheus
  - URL: https://github.com/bigsk1/jarvis-voice

### Voz y agentes from-scratch
- **Karan-Negi-12/Project-Jarvis** — ReAct loop, 3-layer memory (working/short-term/long-term), openWakeWord, ECAPA-TDNN speaker verification, ChromaDB, tool registry con permissions
  - URL: https://github.com/Karan-Negi-12/Project-Jarvis
- **retr0-1337/jarvis** — Fully offline: Whisper+Ollama+edge-tts, agentic self-correcting loop (generate→run→test→fix→retry), WebRTC VAD, Docker sandbox, CVE database
  - URL: https://github.com/retr0-1337/jarvis

### UI y experiencia
- **kaustav991a/J.A.R.V.I.S** — React+Vite+GSAP holographic HUD, FastAPI+WebSocket backend, Picovoice wake word, Piper TTS, YOLOv8+DeepFace vision, ChromaDB
  - URL: https://github.com/kaustav991a/J.A.R.V.I.S
- **cid-moosa/jarvis-ai-assistant** — Jarvis v2.0, RapidFuzz intent matching, glassmorphic WebUI, double-clap trigger, OpenCV camera skill, dual TTS (Edge-TTS + SAPI5)
  - URL: https://github.com/cid-moosa/jarvis-ai-assistant
- **deepakrakshit/jarvis** — Reliability-first, Plan→Validate→Execute→Synthesize agent loop, Three.js plasma UI, document intelligence, screen awareness
  - URL: https://github.com/deepakrakshit/jarvis

### Arquitectura avanzada
- **vierisid/jarvis** — Always-on daemon con Go sidecars, 9 specialist agents, visual workflow builder (n8n-style, 50+ nodes), authority gating, JWT WebSocket
  - URL: https://github.com/vierisid/jarvis
- **JEGAN-tom/Tom-s-Assistant** — Cyberpunk pywebview desktop, Flask-SocketIO mobile mirror, Gemini Vision screen watcher, autonomous agent engine con JSON planner
  - URL: https://github.com/JEGAN-tom/Tom-s-Assistant

## Stack confirmado ARIA App
- Backend: FastAPI + Uvicorn (actual) → migrar a multi-agente
- Voz: edge-tts (actual) → + faster-whisper/Vosk + openWakeWord + Piper
- Personalidad: system prompt + memoria JSON (actual) → 3-layer memory + ChromaDB
- Skills: sistema modular simple (actual) → 27 skills + Tool RAG + MCP
- Frontend: HTML+JS vanilla (actual) → React+Vite+Three.js HUD (futuro)
- Datos: memoria en JSON (actual) → SQLite + ChromaDB + dual DB
- Desktop: PowerShell scripts + acceso directo (actual) → daemon + sidecar (futuro)

## Rutas API actuales
- GET /health
- GET /api/system/status
- POST /api/chat
- GET /api/skills
- POST /api/skills/{name}
- POST /api/tts/speak
- GET /api/tts/voices
- GET /api/ai/status
- GET /api/memory/recent
- POST /api/memory/save

## Próximos pasos
Ver MEJORAS_REFERENCIAS.md para plan detallado por fases.
