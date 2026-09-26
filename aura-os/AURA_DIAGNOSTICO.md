# AURA Virtual Assistant — Diagnostic & Gap Analysis
# References: Ultron (51ultron, Live-agent-Ultron, ULTRON autonomous agent)
#             JARVIS (Project-JARVIS, rishaadj/JARVIS, vannu07/jarvis)

## 1. Estado actual de AURA

### Backend
- FastAPI + Uvicorn
- main_minimal.py ✅ (funciona en Windows)
- main.py completo con muchos routers, pero requiere dependencias pesadas (selenium, mediapipe, opencv, etc.)
- voice_manager.py — STT/TTS simulado (stub)
- voice_routes.py — rutas de voz
- gui_automation_engine.py — captura de pantalla básica con pyautogui
- brain_orchestrator.py — orquestación
- memory router — memoria vectorial
- AI router — enrutamiento de modelos
- 30+ routers especializados

### Windows Native
- venv creado en C:\Users\User\Downloads\AURA\aura-os\venv
- .env configurado
- Acceso directo en escritorio: AURA OS
- Backend mínimo funcionando en puerto 8000
- Dependencias instaladas: fastapi, uvicorn, pydantic, sqlalchemy, requests, etc.

### Faltante en backend
- [ ] STT real (Speech-to-Text) — actualmente solo stub
- [ ] TTS real (Text-to-Speech) — actualmente solo stub
- [ ] Wake word detection
- [ ] Frontend/HUD web funcional (solo HTML básico)
- [ ] Memoria persistente real (vector store)
- [ ] Skills/plugins system
- [ ] Control del sistema operativo
- [ ] Integración con modelos IA reales (Gemini, Groq, etc.)
- [ ] WebSocket para voz en tiempo real

## 2. Referencias analizadas

### Ultron (51ultron.com)
Arquitectura:
- Frontend: Next.js 14 App Router
- Backend: API routes + skills registry (57 skills)
- Model tiers: Minuet, Allegro, Forte, Plinth
- Sandbox por conversación en Kubernetes
- Supabase + pgvector para embeddings
- Workers: cron, marketing-swarm, inference relay
- MCP servers para herramientas externas

### Live-agent-Ultron (Uncle-Noon)
- Frontend: HTML/CSS/JS vanilla (estático)
- Backend: Node.js + Express
- IA: Google Gemini 2.0 Flash
- Voz: Web Speech API (STT/TTS browser)
- Seguridad: API key solo server-side
- Docker + Cloud Run deployment

### ULTRON Autonomous Agent (ASHOKMUKHERJEE6)
- Multi-agente: Planner, Executor, Monitor, Evaluator, Goal
- Visión de pantalla en tiempo real
- Control local del sistema
- Web automation con Playwright
- Monitor hardware (CPU, RAM, GPU)
- Dashboard web remoto
- TTS/STT integrados

### Project-JARVIS (JarvisOSLinux)
- CLI + TUI + voz
- MCP para herramientas dinámicas
- Ollama por defecto (local)
- Contextor (memoria vectorial Rust)
- dmcp (MCP server manager Rust)
- dispatch (ejecutor paralelo Rust)
- Skills externos indexados

### rishaadj/JARVIS
- Python + Flask + SocketIO
- Vosk (STT offline)
- Edge-TTS / gTTS
- Control de apps, WhatsApp, YouTube
- Visión de pantalla
- Memoria local

### vannu07/jarvis
- Python + OpenCV + SQLite
- Reconocimiento facial
- Hotword detection
- Web UI moderna
- Weather, Wikipedia, system stats

## 3. Gap Analysis — Qué falta para que AURA funcione como Ultron/Jarvis

### Crítico (sin esto no funciona como asistente)
1. **STT real** — grabar micrófono y convertir a texto
   - Opción A: Vosk (offline, ligero)
   - Opción B: Whisper local
   - Opción C: Web Speech API (browser)
   - Referencia: rishaadj/JARVIS usa Vosk

2. **TTS real** — convertir texto a voz
   - Opción A: Edge-TTS (Microsoft, gratis, buena calidad)
   - Opción B: pyttsx3 (offline)
   - Opción C: gTTS (Google, requiere internet)
   - Referencia: Project-JARVIS usa Edge-TTS, pyjarvis usa Edge-TTS

3. **Frontend/HUD funcional**
   - Opción A: HTML/JS vanilla como Live-agent-Ultron
   - Opción B: React/Next.js como Ultron
   - Opción C: PyQt6/Tauri como ULTRON desktop
   - Referencia: vannu07/jarvis tiene UI web moderna

4. **Integración con IA real**
   - Conectar a Gemini/Groq/OpenAI/Ollama
   - El backend tiene ai_router.py pero no está conectado al frontend
   - Referencia: Ultron usa 4 tiers de modelos

### Importante (mejora la experiencia)
5. **Memoria persistente**
   - Vector store para conversaciones
   - Referencia: Project-JARVIS tiene Contextor (Rust)
   - Referencia: Ultron tiene Memory Hub con tiers HOT/WARM/COLD

6. **Skills/plugins system**
   - Sistema de habilidades extensible
   - Referencia: Ultron tiene 57 skills + MCP servers
   - Referencia: Project-JARVIS tiene skill discovery semántica

7. **Control del sistema**
   - Abrir apps, control volumen, brightness
   - Referencia: ULTRON autonomous agent tiene GUI automation
   - Referencia: rishaadj/JARVIS controla apps, WhatsApp, YouTube

8. **WebSocket en tiempo real**
   - Para voz streaming
   - Referencia: Ultron tiene WebSocket en /ws/telemetry
   - Referencia: Project-JARVIS tiene socket interface

### Nice-to-have
9. **Wake word detection**
   - "Hey AURA"
   - Referencia: Ultron (Android) usa Picovoice Porcupine
   - Referencia: vannu07/jarvis tiene hotword detection

10. **Multi-modal**
    - Visión de pantalla
    - Cámara
    - Referencia: ULTRON autonomous agent tiene screen vision

11. **Auto-mejora continua**
    - Self-learning
    - Referencia: Ultron tiene Trajectory Hub + auto-evolución

## 4. Plan de acción priorizado

### Fase 1: Funcionalidad básica (semana 1)
1. Integrar STT real (Vosk o Whisper)
2. Integrar TTS real (Edge-TTS)
3. Mejorar frontend web para chat de voz
4. Conectar a un modelo IA real (Gemini/Groq/Ollama)
5. Probar ciclo completo: voz → IA → voz

### Fase 2: Experiencia de usuario (semana 2)
6. HUD/UI moderna tipo Jarvis
7. Memoria persistente (SQLite + embeddings)
8. Skills básicas (abrir apps, búsquedas, system stats)
9. Control del sistema (volume, brightness, apps)

### Fase 3: Avanzado (semana 3+)
10. Wake word detection
11. Multi-agente (Planner, Executor, Monitor)
12. Auto-mejora continua
13. MCP tools integration

## 5. Referencias útiles

### Repos
- https://github.com/Uncle-Noon/Live-agent-Ultron — HTML/JS + Gemini
- https://github.com/ASHOKMUKHERJEE6/ULTRON_AUTONOMUS_AGENT — Multi-agente + visión
- https://github.com/JarvisOSLinux/Project-JARVIS — MCP + Rust + Ollama
- https://github.com/rishaadj/JARVIS — Vosk + Edge-TTS + control apps
- https://github.com/vannu07/jarvis — Face recognition + hotword

### Stack recomendado para AURA
- **STT**: Vosk (offline, rápido) o Whisper (más preciso)
- **TTS**: Edge-TTS (gratis, buena calidad)
- **Frontend**: HTML/CSS/JS vanilla + WebSocket (como Live-agent-Ultron)
- **Backend**: FastAPI + WebSocket (ya existe)
- **Memoria**: SQLite + FAISS/ChatGPT embeddings
- **IA**: Groq/Gemini/Ollama según disponibilidad
- **Control sistema**: pyautogui + pygetwindow
