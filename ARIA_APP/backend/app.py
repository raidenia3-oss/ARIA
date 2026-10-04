"""ARIA App Backend — FastAPI with multi-agent ReAct Loop, Tool Registry, and 3-layer memory."""

import asyncio
import json
import os
import random
import string
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Load .env BEFORE any router imports so GITHUB_TOKEN etc. are available at module init
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=True)
except Exception:
    pass

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR.parent))
sys.path.insert(0, str(APP_DIR))

# Ensure project-root backend package is importable (knowledge module lives there)
_project_backend = str(APP_DIR.parent / "backend")
if _project_backend not in sys.path:
    sys.path.insert(0, _project_backend)

# Ensure ARIA_APP/backend is importable (github_admin, api modules live here)
_aria_app_backend = str(APP_DIR)
if _aria_app_backend not in sys.path:
    sys.path.insert(0, _aria_app_backend)

try:
    from ai_providers import AIProviderManager

    ai_manager = AIProviderManager()
    AI_ENABLED = True
    AI_UNAVAILABLE_REASON = ""
except Exception as exc:  # noqa: BLE001 - se registra el motivo, no se traga
    AI_ENABLED = False
    AI_UNAVAILABLE_REASON = f"{type(exc).__name__}: {exc}"
    logging.getLogger(__name__).error(
        "AIProviderManager no disponible, ARIA_APP arranca sin proveedor de IA: %s",
        AI_UNAVAILABLE_REASON,
    )

    class _FallbackAIManager:
        """Superficie minima para que la UI no reviente cuando no hay IA.

        No finge estar sana: ningun proveedor se ha sondeado, asi que
        `available` es `None` (no `True`) y `chat()` devuelve un aviso del
        sistema, no una respuesta del modelo. `latency` no se inventa.
        """

        def __init__(self):
            self.unavailable_reason = AI_UNAVAILABLE_REASON
            self.providers = {
                "local": {
                    "available": None,
                    "available_reason": "provider not probed: import failed",
                    "priority": 99,
                }
            }
            self._usage = {"requests": 0, "tokens": 0, "providers_used": {}}
            self._circuit_breaker = {}
            self._latency_history = {}

        def chat(self, message, history=None, system_prompt="", provider=None):
            return {
                "message": (
                    "IA no disponible: ningun proveedor resolvio al arrancar "
                    f"({self.unavailable_reason or 'motivo desconocido'}). "
                    "Esto lo dice el sistema, no un modelo."
                ),
                "provider": None,
                "data_source": "unavailable",
                "detail": self.unavailable_reason,
                "latency": None,
            }

        def get_available_providers(self):
            return []

        def get_best_provider(self):
            return None

        def get_provider_health(self):
            return {
                name: {
                    "available": None,
                    "available_reason": "provider not probed: import failed",
                    "circuit_open": None,
                    "avg_latency": None,
                    "failures": None,
                }
                for name in self.providers
            }

    ai_manager = _FallbackAIManager()

FRONTEND_DIR = APP_DIR / "frontend"
MEMORY_DIR = APP_DIR / "memory"
MEMORY_DIR.mkdir(exist_ok=True)

from backend.agent.core import ReactLoop

# Daemon and Sync Modules
from backend.daemon.cross_device_sync import CrossDeviceSync
from backend.daemon.daemon_orchestrator import DaemonOrchestrator
from backend.memory.long_term import LongTermMemory
from backend.memory.short_term import ShortTermMemory
from backend.memory.working import WorkingMemory
from backend.skills.registry import SkillRegistry
from backend.voice.pipeline import STTPipeline, TTSPipeline, WakeWordDetector
from backend.safety_filter import get_blocked_patterns_count
from backend.tool_registry import ToolRegistry

# Initialize modules
cross_device_sync = CrossDeviceSync()
daemon_orchestrator = DaemonOrchestrator()
daemon_orchestrator.start()
from backend.agent.social_research_agent import SocialResearchAgent
from backend.agents.kilo_bridge import KiloTask, kilo_bridge
from backend.api.compat import router as openai_router
from backend.api.core_routes import router as core_router
from backend.api.ai_infrastructure import router as ai_infrastructure_router
from backend.api.vector_memory import router as vector_memory_router
from backend.api.longmemory_wrapper import router as longmemory_router
from backend.api.longmemory_wrapper import StoreRequest, RetrieveRequest
from backend.api.candle_llm import router as candle_router
from backend.api.computer_use import router as computer_use_router
from backend.api.github_webhooks import router as github_webhook_router
from backend.automation import automation_engine, enable_autostart, scheduler_router
from backend.automation.models import AutomationRuleModel
from backend.daemon.sync_routes import router as daemon_sync_router
from backend.evolution.engine import SkillEvolution
from backend.evolution.patcher import router as evolution_router
from backend.knowledge.router import router as knowledge_router
from backend.learning.compound import CompoundLearning
from backend.planner.planner_routes import router as planner_router
from backend.plugins import plugin_manager
from backend.proactive.engine import ProactiveSystem
from backend.resilience.self_healing import router as self_healing_router
from backend.security.zk_routes import router as zk_router
from backend.social_research.analyzer import VideoAnalyzer
from backend.social_research.classifier import ContentClassifier, ContentProfile, ImportanceScore
from backend.social_research.collector import SocialCollector
from backend.social_research.memory_bridge import MemoryBridge, SavedContent
from backend.social_research.transcriber import WhisperTranscriber
from backend.swarm.swarm_routes import router as swarm_router
from backend.api.swarm_router import router as agent_swarm_router
from api.agent_harness import router as harness_router
from backend.video_analyzer.pipeline import VideoAnalysisPipeline
from backend.vision.screen import ScreenIntelligence
from github_admin.router import router as github_admin_router

# ARIA Visual + Observer Integration
try:
    from ARIA_APP.frontend.aria_observer import AriaObserver

    aria_observer = AriaObserver(backend_url="http://localhost:8000", poll_interval=2)
    ARIA_ENABLED = True
except Exception:
    try:
        from ARIA_APP.frontend.aria_observer import AriaObserver

        aria_observer = AriaObserver(backend_url="http://localhost:8000", poll_interval=2)
        ARIA_ENABLED = True
    except Exception:
        aria_observer = None
        ARIA_ENABLED = False

try:
    from backend.aria_engine import AriaEngine

    aria_engine = AriaEngine(ai_manager)
    ARIA_ENGINE_ENABLED = True

    # USB Intelligence and Adaptive Engine imports
    try:
        from backend.usb_intelligence import handle_usb_status, handle_usb_expansion
        from backend.aria_adaptive_engine import handle_aria_auto
        USB_INTELLIGENCE_ENABLED = True
    except Exception:
        USB_INTELLIGENCE_ENABLED = False
except Exception:
    try:
        from backend.aria_engine import AriaEngine

        aria_engine = AriaEngine(ai_manager)
        ARIA_ENGINE_ENABLED = True
    except Exception:
        aria_engine = None
        ARIA_ENGINE_ENABLED = False

ARIA_SAFETY_ENABLED = True

try:
    from backend.ml.dataset_builder import DatasetBuilder

    dataset_builder = DatasetBuilder()
    ML_ENABLED = True
except Exception:
    try:
        from ml.dataset_builder import DatasetBuilder

        dataset_builder = DatasetBuilder()
        ML_ENABLED = True
    except Exception:
        dataset_builder = None
        ML_ENABLED = False

try:
    from backend.ml.lora_trainer import LoRATrainer

    lora_trainer = LoRATrainer()
    LORA_ENABLED = True
except Exception:
    try:
        from ml.lora_trainer import LoRATrainer

        lora_trainer = LoRATrainer()
        LORA_ENABLED = True
    except Exception:
        lora_trainer = None
        LORA_ENABLED = False

try:
    from backend.generation.content_generator import (
        AnimePromptOptimizer,
        CharacterDesigner,
        ContentLibrary,
        StoryGenerator,
        WorldBuilder,
    )

    content_lib = ContentLibrary()
    story_gen = StoryGenerator()
    char_designer = CharacterDesigner()
    world_builder = WorldBuilder()
    prompt_opt = AnimePromptOptimizer()
    GENERATION_ENABLED = True
except Exception:
    try:
        from generation.content_generator import (
            AnimePromptOptimizer,
            CharacterDesigner,
            ContentLibrary,
            StoryGenerator,
            WorldBuilder,
        )

        content_lib = ContentLibrary()
        story_gen = StoryGenerator()
        char_designer = CharacterDesigner()
        world_builder = WorldBuilder()
        prompt_opt = AnimePromptOptimizer()
        GENERATION_ENABLED = True
    except Exception:
        story_gen = None
        char_designer = None
        world_builder = None
        prompt_opt = None
        content_lib = None
        GENERATION_ENABLED = False

# ARIA Content Engine imports
_gen_path = str(APP_DIR / "generation")
if _gen_path not in sys.path:
    sys.path.insert(0, _gen_path)
_gen_path2 = str(APP_DIR / "backend")
if _gen_path2 not in sys.path:
    sys.path.insert(0, _gen_path2)

try:
    from backend.aria_content_engine import AriaContentEngine

    aria_content_engine = AriaContentEngine()
    ARIA_CONTENT_ENABLED = True
except Exception:
    try:
        from backend.aria_content_engine import AriaContentEngine

        aria_content_engine = AriaContentEngine()
        ARIA_CONTENT_ENABLED = True
    except Exception:
        aria_content_engine = None
        ARIA_CONTENT_ENABLED = False

skill_registry = SkillRegistry()
working_memory = WorkingMemory()
short_term_memory = ShortTermMemory(path=str(MEMORY_DIR / "short_term.json"))
short_term_memory.load()
long_term_memory = LongTermMemory(path=str(MEMORY_DIR / "long_term.json"))
long_term_memory.load()

social_agent = SocialResearchAgent()
video_pipeline = VideoAnalysisPipeline()

stt_pipeline = STTPipeline()
tts_pipeline = TTSPipeline()
wake_detector = WakeWordDetector()
screen_intelligence = ScreenIntelligence()
proactive = ProactiveSystem()
evolution = SkillEvolution()
compound = CompoundLearning()

react_loop = ReactLoop(
    skill_registry=skill_registry,
    memory=short_term_memory,
    ai_manager=ai_manager,
)

from datetime import timedelta

_context_cache = {}
_cache_timestamp = None
_CACHE_TTL = 3

def _get_cached_context():
    global _context_cache, _cache_timestamp
    now = datetime.now()
    if _cache_timestamp and (now - _cache_timestamp) < timedelta(seconds=_CACHE_TTL):
        return _context_cache
    return None

def _cache_context(context):
    global _context_cache, _cache_timestamp
    _context_cache = context
    _cache_timestamp = datetime.now()

app = FastAPI(title="ARIA App", version="2.0.0")

app.include_router(self_healing_router, prefix="/api/resilience")

app.add_middleware(
    CORSMiddleware,
    # Origins explicitos, no "*": con allow_credentials=True el comodin hace que
    # el navegador acepte el credential de cualquier origen. Sin "null"/"file://":
    # el renderer Electron llama por IPC, no por HTTP directo al backend.
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "AURA_CORS_ORIGINS",
            "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000",
        ).split(",")
        if origin.strip()
    ],
    # allow_credentials=True SOLO con origins literales: si AURA_CORS_ORIGINS trae
    # "*" hay que pasarlo a False.
    allow_credentials="*" not in os.getenv("AURA_CORS_ORIGINS", ""),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-Hub-Signature-256",
    ],
)

app.include_router(core_router)
app.include_router(ai_infrastructure_router)
app.include_router(vector_memory_router)
app.include_router(longmemory_router)
app.include_router(candle_router)
app.include_router(computer_use_router)
app.include_router(github_webhook_router)
app.include_router(openai_router)
app.include_router(scheduler_router)

from fastapi import APIRouter
daemon_sync_router = APIRouter()


def sync_endpoint():
    nodes_list = list(cross_device_sync.nodes.values())
    first_sync = nodes_list[0].last_sync.isoformat() if nodes_list else None
    return {
        "status": "synchronized",
        "nodes": [node.node_id for node in cross_device_sync.nodes.values()],
        "last_sync": first_sync,
    }


def daemon_status_endpoint():
    return {
        "daemon": {
            "is_running": daemon_orchestrator.health.is_running,
            "uptime_seconds": daemon_orchestrator.health.uptime_seconds,
            "last_check": daemon_orchestrator.health.last_check.isoformat(),
        }
    }


@daemon_sync_router.get("/api/daemon/sync")
async def get_sync_status():
    return sync_endpoint()


@daemon_sync_router.get("/api/daemon/status")
async def get_daemon_status():
    return daemon_status_endpoint()


app.include_router(daemon_sync_router)
app.include_router(knowledge_router)
app.include_router(evolution_router)
app.include_router(planner_router)
app.include_router(swarm_router)
app.include_router(agent_swarm_router)
app.include_router(harness_router)
app.include_router(zk_router)
app.include_router(github_admin_router)
enable_autostart()


@app.on_event("startup")
async def _plugin_startup():
    await plugin_manager.execute_hook_async("on_startup")

    asyncio.create_task(automation_engine.start_monitoring())
    print("[Startup] Automation monitoring started")
    if ARIA_ENABLED and aria_observer:
        aria_observer.start()
        print("[Startup] ARIA Observer started")


@app.on_event("shutdown")
async def _plugin_shutdown():
    await plugin_manager.execute_hook_async("on_shutdown")


class ChatRequest(BaseModel):
    message: str
    mode: str = "text"
    session_id: str | None = None


class SkillRequest(BaseModel):
    params: dict = {}


class MemorySaveRequest(BaseModel):
    content: str
    type: str = "fact"
    meta: dict = {}


@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "mode": "ARIA-app-v2", "timestamp": time.time()})


@app.get("/api/system/status")
def system_status():
    try:
        import psutil

        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory().percent
        disk = psutil.disk_usage(os.path.expanduser("~")).percent
        status = {
            "backend": "running",
            "cpu": cpu,
            "memory": mem,
            "disk": disk,
            "mode": "ARIA-app-v2",
            "version": "2.0.0",
        }
        if AI_ENABLED:
            status["ai"] = {
                "enabled": True,
                "providers": ai_manager.get_available_providers(),
                "best": ai_manager.get_best_provider(),
            }
        status["skills"] = len(skill_registry.list())
        # OJO: "memory" YA es el % de RAM que consume el HUD (ramVal / ramFill).
        # Antes se sobrescribía con un dict y el panel RAM mostraba "[object Object]".
        # El detalle va en "memory_stats".
        status["memory_stats"] = {
            "short_term": len(short_term_memory.recent(200)),
            "long_term": len(long_term_memory.all(200)),
        }
        return JSONResponse(status)
    except Exception as e:
        return JSONResponse({"backend": "running", "error": str(e), "mode": "ARIA-app-v2"})


@app.get("/api/system/health")
def system_health():
    """Salud global consumida por el HUD (panel "Salud Global" + subsistemas).

    Antes esta ruta no existía en este runtime -> el HUD mostraba 'offline' fijo.
    Si Ollama está caído se reporta 'degraded' (el HUD pinta el núcleo en ámbar).
    """
    ai_manager_ok = False
    try:
        ai_manager_ok = bool(ai_manager.ping())
    except Exception:
        ai_manager_ok = False

    try:
        daemon_state = {
            "running": bool(getattr(daemon_orchestrator.health, "is_running", False)),
            "uptime_seconds": getattr(daemon_orchestrator.health, "uptime_seconds", 0),
        }
    except Exception:
        daemon_state = {"running": False, "uptime_seconds": 0}

    peers = 0
    try:
        peers = len(cross_device_sync.nodes)
    except Exception:
        peers = 0

    skills_count = 0
    try:
        skills_count = len(skill_registry.list())
    except Exception:
        skills_count = 0

    issues = [] if ai_manager_ok else ["ollama_offline"]
    return JSONResponse(
        {
            "status": "healthy" if not issues else "degraded",
            "issues": issues,
            "services": {
                "backend": {"state": "running"},
                "ollama": {"state": "up" if ai_manager_ok else "down"},
                "skills": {"state": "up", "count": skills_count},
            },
            "jan": None,  # no hay módulo JAN en este runtime (el HUD muestra '--')
            "websocket": {"status": "up", "endpoint": "/api/aria/observe"},
            "mdns_peers": {"count": peers},
            "mobile_sync": {"status": "idle", "nodes": peers},
            "daemon": daemon_state,
            "timestamp": time.time(),
        }
    )


# P2P Reconcile (Bloque 50): el router vive en backend/p2p_reconcile.py y su
# /status alimenta el panel P2P del HUD. Antes sólo se montaba en backend/main.py,
# por eso /api/sync/reconcile/status devolvía 404 en este runtime.
try:
    from backend.p2p_reconcile import router as p2p_reconcile_router

    # El motor P2P resuelve su estado con os.getcwd() y este runtime hace chdir a
    # ARIA_APP -> leería ARIA_APP/data y el panel P2P mostraría siempre ceros.
    # Se fija el directorio del proyecto si no hay override por entorno.
    os.environ.setdefault("ARIA_SYNC_DIR", str(APP_DIR.parent / "data"))
    app.include_router(p2p_reconcile_router)
except Exception as _p2p_exc:  # el HUD degrada a '--' si no está montado
    print(f"[AURA] p2p_reconcile no montado: {_p2p_exc}")


_ARIA_ROUTER = None


def _get_aria_router():
    """Shared AIRouter instance so provider scores and circuit state persist in-process."""
    global _ARIA_ROUTER
    if _ARIA_ROUTER is None:
        from backend.ai_router import AIRouter
        _ARIA_ROUTER = AIRouter()
    return _ARIA_ROUTER


@app.post("/api/chat")
async def chat(req: ChatRequest):
    text = (req.message or "").strip()
    await plugin_manager.execute_hook_async(
        "on_chat", text, {"timestamp": datetime.now().isoformat()}
    )

    if not text:
        raise HTTPException(status_code=400, detail="message vacío")

    await automation_engine.check_and_execute(
        {"event": "chat_received", "message": text, "timestamp": datetime.now().isoformat()}
    )
    session_id = req.session_id or str(int(time.time() * 1000))
    working_memory.set(session_id, "last_user_message", text)
    system_prompt = os.environ.get(
        "ARIA_SYSTEM_PROMPT",
        "Eres ARIA, un asistente personal avanzado estilo Jarvis/Ultron. Responde en español, conciso, útil y con personalidad propia.",
    )

    # --- LongMemory episodic context ---
    episodic_context = ""
    try:
        from backend.api.longmemory_wrapper import retrieve_memory as _lm_retrieve
        mem_req = RetrieveRequest(query=text, top_k=3, mode="associative")
        mem_result = await _lm_retrieve(mem_req)
        if mem_result.status == "success" and mem_result.results:
            lines = []
            for item in mem_result.results:
                node = item.get("node", {}) if isinstance(item, dict) else {}
                content = node.get("content", {}) if isinstance(node, dict) else {}
                summary = content.get("summary", "") if isinstance(content, dict) else ""
                if summary:
                    lines.append(f"- {summary}")
            if lines:
                episodic_context = (
                    "\n\nContexto episódico de conversaciones previas:\n"
                    + "\n".join(lines)
                )
    except Exception:
        pass  # LongMemory no disponible — continuar sin contexto

    if episodic_context:
        system_prompt = system_prompt + episodic_context

    # --- AIRouter: canonical multi-provider gateway (Mistral → DeepSeek → Ollama) ---
    if AI_ENABLED:
        try:
            decision = await _get_aria_router().generate_response(
                text,
                context={"session_id": session_id},
                system_prompt=system_prompt,
                max_tokens=512,
            )
            routed_text = decision.get("message") or ""
            if routed_text.strip():
                working_memory.set(session_id, "last_response", routed_text)
                working_memory.set(session_id, "last_provider", decision.get("provider"))
                await _store_chat_memory(text, routed_text)
                return JSONResponse(
                    {
                        "response": routed_text,
                        "timestamp": time.time(),
                        "mode": req.mode,
                        "session_id": session_id,
                        "provider": decision.get("provider"),
                        "latency": decision.get("latency"),
                        "tokens": decision.get("tokens"),
                    }
                )
        except Exception:
            pass  # router unavailable — falls through to Candle/Ollama/ReAct

    # --- Provider priority: Candle → Ollama → ReAct loop ---
    # Candle.rs (v5.2+) is fastest (~5-8s), Ollama is default (~15s)
    from backend.api.candle_llm import is_candle_available, CandleInferenceRequest as _CandleReq

    if is_candle_available():
        try:
            started = time.time()
            from backend.api.candle_llm import candle_inference as _candle_inf
            candle_req = _CandleReq(prompt=text, system_prompt=system_prompt)
            candle_result = await _candle_inf(candle_req)
            response_text = candle_result.response
            working_memory.set(session_id, "last_response", response_text)
            working_memory.set(session_id, "last_provider", "candle")
            await _store_chat_memory(text, response_text)
            return JSONResponse(
                {
                    "response": response_text,
                    "timestamp": time.time(),
                    "mode": req.mode,
                    "session_id": session_id,
                    "provider": "candle",
                    "latency": candle_result.latency_ms / 1000,
                    "tokens": candle_result.tokens,
                }
            )
        except Exception:
            pass  # fallback to Ollama

    if AI_ENABLED and ai_manager.get_best_provider() == "ollama":
        # Ruta rápida y directa a Ollama local (sin pasar por el ReAct loop)
        try:
            started = time.time()
            result = ai_manager.chat(text, system_prompt=system_prompt, provider="ollama")
            response_text = result.get("message", "")
            working_memory.set(session_id, "last_response", response_text)
            working_memory.set(session_id, "last_provider", "ollama")
            await _store_chat_memory(text, response_text)
            return JSONResponse(
                {
                    "response": response_text,
                    "timestamp": time.time(),
                    "mode": req.mode,
                    "session_id": session_id,
                    "provider": "ollama",
                    "latency": result.get("latency", round(time.time() - started, 2)),
                    "tokens": result.get("tokens", 0),
                }
            )
        except Exception:
            pass  # cae al ReAct loop como respaldo
    result = react_loop.run(text, system_prompt=system_prompt)
    response_text = result.get("response", "")
    working_memory.set(session_id, "last_response", response_text)
    working_memory.set(session_id, "last_provider", result.get("provider", "local"))
    await _store_chat_memory(text, response_text)
    return JSONResponse(
        {
            "response": response_text,
            "timestamp": time.time(),
            "mode": req.mode,
            "session_id": session_id,
            "provider": result.get("provider"),
            "latency": result.get("latency"),
            "plan": result.get("plan"),
            "executed_steps": result.get("executed_steps"),
            "validation_errors": result.get("validation_errors"),
        }
    )


async def _store_chat_memory(query: str, response: str):
    """Store conversation in LongMemory (best-effort, non-blocking)."""
    try:
        from backend.api.longmemory_wrapper import store_memory as _lm_store
        store_req = StoreRequest(query=query, response=response)
        await _lm_store(store_req)
    except Exception:
        pass


class ChatStreamRequest(BaseModel):
    message: str = ""
    session_id: Optional[str] = None
    mode: str = "text"
    history: Optional[List[List[str]]] = None
    system_prompt: Optional[str] = None


@app.post("/api/chat/stream")
async def chat_stream(req: ChatStreamRequest):
    """Streaming SSE directo desde Ollama: el HUD renderiza token a token."""
    from fastapi.responses import StreamingResponse

    text = (req.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="message vacío")
    if not AI_ENABLED:
        raise HTTPException(status_code=503, detail="AI no disponible")
    session_id = req.session_id or str(int(time.time() * 1000))
    system_prompt = (req.system_prompt or "").strip() or os.environ.get(
        "ARIA_SYSTEM_PROMPT",
        "Eres ARIA, un asistente personal avanzado estilo Jarvis/Ultron. Responde en español, conciso, útil y con personalidad propia.",
    )
    history = req.history or []

    # --- LongMemory episodic context ---
    try:
        from backend.api.longmemory_wrapper import retrieve_memory as _lm_retrieve
        mem_req = RetrieveRequest(query=text, top_k=3, mode="associative")
        mem_result = await _lm_retrieve(mem_req)
        if mem_result.status == "success" and mem_result.results:
            lines = []
            for item in mem_result.results:
                node = item.get("node", {}) if isinstance(item, dict) else {}
                content = node.get("content", {}) if isinstance(node, dict) else {}
                summary = content.get("summary", "") if isinstance(content, dict) else ""
                if summary:
                    lines.append(f"- {summary}")
            if lines:
                system_prompt = system_prompt + (
                    "\n\nContexto episódico de conversaciones previas:\n"
                    + "\n".join(lines)
                )
    except Exception:
        pass

    def gen():
        full = []
        try:
            for piece in ai_manager.chat_stream_ollama(
                text, history=history, system_prompt=system_prompt
            ):
                full.append(piece)
                yield f"data: {json.dumps({'token': piece}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        working_memory.set(session_id, "last_response", "".join(full))
        working_memory.set(session_id, "last_provider", "ollama")
        # Store conversation in LongMemory (best-effort, sync HTTP call)
        try:
            from backend.api.longmemory_wrapper import _lm_request
            _lm_request("POST", "/v1/ingest", {
                "user_id": "aria",
                "text": f"User: {text}\nAssistant: {''.join(full)}",
                "metadata": {},
                "facet_hint": "episodic",
            })
        except Exception:
            pass
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/ai/ollama")
def ollama_status():
    """Estado de Ollama local + modelos instalados (re-detectado en vivo)."""
    if not AI_ENABLED:
        return JSONResponse({"online": False, "models": [], "active": None, "installed": False})
    try:
        info = ai_manager.refresh_ollama()
        return JSONResponse(
            {
                "online": info.get("online", False),
                "models": info.get("models", []),
                "active": info.get("active"),
                "installed": info.get("installed", False),
            }
        )
    except Exception:
        pass
    try:
        models = ai_manager.list_ollama_models()
    except Exception:
        models = []
    online = ai_manager.ping() if hasattr(ai_manager, "ping") else bool(models)
    return JSONResponse(
        {
            "online": online,
            "models": models,
            "active": os.environ.get("LOCAL_LFM_MODEL", "dolphin-2_6-phi-2:latest"),
            "installed": True,
        }
    )


@app.get("/api/skills")
def list_skills():
    return JSONResponse({"skills": skill_registry.list(), "count": len(skill_registry.list())})


@app.post("/api/skills/{skill_name}")
async def run_skill(skill_name: str, payload: SkillRequest | None = None):
    params = (payload.params if payload else {}) or {}
    await plugin_manager.execute_hook_async("on_skill_execute", skill_name, params)
    result = skill_registry.run(skill_name, params)
    return JSONResponse(result)


@app.get("/api/skills/search")
def search_skills(q: str = "", top_k: int = 5):
    q = (q or "").strip()
    if not q:
        return JSONResponse({"query": q, "results": skill_registry.list()[:top_k]})
    return JSONResponse({"query": q, "results": skill_registry.search(q, top_k=top_k)})


@app.post("/api/self-improvement/start")
async def start_self_improvement():
    """Start autonomous self-improvement cycle"""
    try:
        result = skill_registry.run('self-improvement', {
            'action': 'cycle',
            'repo': 'raidenia3-oss/ARIA',
            'auto_commit': True,
            'auto_pr': True,
            'auto_release': False
        })
        return JSONResponse({
            "status": "success",
            "message": "Self-improvement cycle started",
            "result": result
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/self-improvement/status")
async def self_improvement_status():
    """Get self-improvement engine status"""
    try:
        from backend.skills.custom.self_improvement import get_self_improvement

        engine = get_self_improvement()
        return JSONResponse({
            "status": "running" if engine._initialized else "stopped",
            "initialized": engine._initialized,
            "github_configured": bool(engine.github_token),
            "repo": engine.repo_name,
            "repo_path": engine.repo_path,
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/api/tts/voices")
def tts_voices():
    return JSONResponse({"voices": ["es-ES-ElviraNeural", "es-AR-ElenaNeural", "en-US-AriaNeural"]})


@app.get("/api/ai/status")
def ai_status():
    if not AI_ENABLED:
        return JSONResponse({"enabled": False, "error": "ai_providers.py no disponible"})
    return JSONResponse(
        {
            "enabled": True,
            "providers": ai_manager.get_provider_health(),
            "available": ai_manager.get_available_providers(),
            "best": ai_manager.get_best_provider(),
            "usage": ai_manager._usage,
        }
    )


@app.post("/api/tts/speak")
def tts_speak(req: dict):
    text = req.get("text", "")
    voice = req.get("voice", "es-ES-ElviraNeural")
    try:
        import asyncio

        import edge_tts

        out_path = APP_DIR / "assets" / "voices" / f"ARIA-{int(time.time())}.mp3"

        async def generate():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(out_path))

        asyncio.run(generate())
        return JSONResponse({"status": "ok", "audio": str(out_path)})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)})


@app.get("/api/memory/recent")
def memory_recent(limit: int = 20, source: str = "short"):
    if source == "long":
        data = long_term_memory.all(limit)
    else:
        data = short_term_memory.recent(limit)
    return JSONResponse({"source": source, "memories": data})


@app.post("/api/memory/save")
def memory_save(req: MemorySaveRequest):
    entry_short = short_term_memory.append(
        req.content, req.content, meta={"type": req.type, **req.meta}
    )
    entry_long = long_term_memory.add(req.content, meta={"type": req.type, **req.meta})
    return JSONResponse({"status": "saved", "short": entry_short, "long": entry_long})


@app.get("/api/memory/search")
def memory_search(q: str = "", limit: int = 20):
    q = (q or "").strip()
    if not q:
        return JSONResponse({"query": q, "results": []})
    results = long_term_memory.search(q, limit=limit)
    return JSONResponse({"query": q, "results": results})


@app.get("/api/agent/status")
def agent_status():
    return JSONResponse(
        {
            "react_loop": "ready",
            "skills_count": len(skill_registry.list()),
            "working_memory_sessions": len(working_memory.all()),
            "short_term_items": len(short_term_memory.recent(200)),
            "long_term_items": len(long_term_memory.all(200)),
            "ai_enabled": AI_ENABLED,
            "voice": {
                "stt": "faster-whisper/vosk",
                "tts": "edge-tts/piper/pyttsx3",
                "wake_word": "openWakeWord",
            },
        }
    )


@app.post("/api/voice/stt")
def voice_stt(req: dict):
    audio_path = req.get("audio_path", "")
    engine = req.get("engine", "auto")
    if not audio_path:
        return JSONResponse({"status": "error", "error": "audio_path requerido"})
    result = stt_pipeline.transcribe(audio_path, engine=engine)
    return JSONResponse(result)


@app.post("/api/voice/tts")
def voice_tts(req: dict):
    text = req.get("text", "")
    voice = req.get("voice", "es-ES-ElviraNeural")
    engine = req.get("engine", "auto")
    if not text:
        return JSONResponse({"status": "error", "error": "text requerido"})
    result = tts_pipeline.speak(text, voice=voice, engine=engine)
    return JSONResponse(result)


@app.post("/api/voice/wake")
def voice_wake(req: dict):
    text = (req.get("text") or "").strip()
    if text:
        # Camino léxico: el STT ya devolvió texto (lo usan el HUD y la app Tk).
        return JSONResponse(wake_detector.detect_text(text, wake_words=req.get("wake_words")))
    audio_path = req.get("audio_path", "")
    threshold = float(req.get("threshold", 0.5))
    if not audio_path:
        return JSONResponse({"status": "error", "error": "requiere 'text' o 'audio_path'"})
    result = wake_detector.listen(audio_path, threshold=threshold)
    return JSONResponse(result)


@app.post("/api/voice/listen")
def voice_listen(req: dict):
    """Pipeline completo STT -> wake-word en una sola llamada (Fase 3: lo usa la app Tk)."""
    audio_path = req.get("audio_path", "")
    engine = req.get("engine", "auto")
    if not audio_path:
        return JSONResponse({"status": "error", "error": "audio_path requerido"})
    stt = stt_pipeline.transcribe(audio_path, engine=engine)
    if stt.get("status") != "ok":
        return JSONResponse({"status": "error", "stage": "stt", "stt": stt})
    text = stt.get("text", "")
    wake = wake_detector.detect_text(text, wake_words=req.get("wake_words"))
    return JSONResponse(
        {
            "status": "ok",
            "text": text,
            "engine": stt.get("engine"),
            "detected": wake.get("detected", False),
            "wake_word": wake.get("wake_word"),
            "command": wake.get("command", ""),
        }
    )


@app.get("/api/voice/status")
def voice_status():
    return JSONResponse(
        {
            "stt": "ready",
            "tts": "ready",
            "default_voice": tts_pipeline.default_voice,
            "wake_word": wake_detector.wake_word,
            "wake_words": wake_detector.wake_words,
            "tts_engines": ["edge-tts", "piper", "pyttsx3"],
        }
    )


@app.post("/api/vision/capture")
def vision_capture(req: dict):
    region = req.get("region")
    result = screen_intelligence.capture(region=tuple(region) if region else None)
    return JSONResponse(result)


@app.post("/api/vision/analyze")
def vision_analyze(req: dict):
    image_path = req.get("image_path")
    result = screen_intelligence.analyze(image_path=image_path)
    return JSONResponse(result)


@app.get("/api/vision/last")
def vision_last():
    return JSONResponse(screen_intelligence.last())


@app.post("/api/video-analyze")
async def video_analyze(req: dict):
    url = req.get("url", "")
    save_if_important = req.get("save_if_important", True)
    if not url:
        return JSONResponse({"status": "error", "error": "url requerido"}, status_code=400)
    try:
        result = video_pipeline.process_url(url, save_if_important=save_if_important)
        return JSONResponse(
            {
                "status": "ok",
                "result": {
                    "url": result.url,
                    "platform": result.platform,
                    "title": result.title,
                    "duration_seconds": result.duration_seconds,
                    "transcription": result.transcription,
                    "visual_analysis": result.visual_analysis,
                    "topics": result.topics,
                    "summary": result.summary,
                    "importance": result.importance,
                    "tags": result.tags,
                    "key_moments": result.key_moments,
                    "saved": result.saved,
                    "content_id": result.content_id,
                    "processing_time": result.processing_time,
                },
            }
        )
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.post("/api/video-analyze/batch")
async def video_analyze_batch(req: dict):
    urls = req.get("urls", [])
    if not urls:
        return JSONResponse({"status": "error", "error": "urls requerido"}, status_code=400)
    try:
        results = video_pipeline.process_batch(urls)
        return JSONResponse(
            {
                "status": "ok",
                "total": len(results),
                "results": [
                    {
                        "url": r.url,
                        "platform": r.platform,
                        "title": r.title,
                        "summary": r.summary,
                        "importance": r.importance,
                        "saved": r.saved,
                        "processing_time": r.processing_time,
                    }
                    for r in results
                ],
            }
        )
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


# =============================================================================
# Social Research Endpoints (direct, due to FastAPI include_router issue)
# =============================================================================

_collector: Optional[SocialCollector] = None
_transcriber: Optional[WhisperTranscriber] = None
_analyzer: Optional[VideoAnalyzer] = None
_classifier: Optional[ContentClassifier] = None
_memory_bridge: Optional[MemoryBridge] = None


def _init_social():
    global _collector, _transcriber, _analyzer, _classifier, _memory_bridge
    if _collector is None:
        _collector = SocialCollector()
    if _transcriber is None:
        _transcriber = WhisperTranscriber(model_size="base")
    if _analyzer is None:
        _analyzer = VideoAnalyzer()
    if _classifier is None:
        _classifier = ContentClassifier()
    if _memory_bridge is None:
        _memory_bridge = MemoryBridge()


class SRCollectReq(BaseModel):
    url: str


class SRCollectBatchReq(BaseModel):
    urls: List[str]


class SRAnalyzeReq(BaseModel):
    video_path: str
    transcription_text: str = ""
    openai_api_key: Optional[str] = None


class SRResearchReq(BaseModel):
    topic: str
    max_results: int = 10
    platforms: List[str] = ["youtube", "instagram", "tiktok"]
    focus_keywords: List[str] = []


class SRSaveReq(BaseModel):
    profile: dict
    transcription_text: str = ""
    visual_desc: str = ""


@app.get("/api/social-research/status")
def social_status():
    _init_social()
    return {
        "collector": {
            "available": _collector.available,
            "platforms": _collector.SUPPORTED_PLATFORMS,
        },
        "transcriber": {"model": _transcriber.model_size, "loaded": _transcriber._model_loaded},
        "analyzer": {
            "vision_model": _analyzer._vision_model,
            "has_client": _analyzer._openai_client is not None,
        },
        "classifier": {"ready": True},
        "memory": {"saved": len(_memory_bridge.library)},
    }


@app.post("/api/social-research/collect")
def social_collect(req: SRCollectReq):
    _init_social()
    if not _collector.is_supported(req.url):
        raise HTTPException(status_code=400, detail=f"URL no soportada: {req.url}")
    try:
        meta = _collector.collect(req.url)
        return {
            "status": "ok",
            "metadata": {
                "url": meta.url,
                "platform": meta.platform,
                "title": meta.title,
                "author": meta.author,
                "duration_seconds": meta.duration_seconds,
                "view_count": meta.view_count,
                "like_count": meta.like_count,
                "thumbnail_path": meta.thumbnail_path,
                "video_path": meta.video_path,
                "audio_path": meta.audio_path,
                "resolution": meta.resolution,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/social-research/collect-batch")
def social_collect_batch(req: SRCollectBatchReq):
    _init_social()
    results = []
    for url in req.urls:
        try:
            meta = _collector.collect(url)
            results.append({"url": url, "status": "ok", "title": meta.title})
        except Exception as e:
            results.append({"url": url, "status": "error", "error": str(e)})
    return {"results": results, "total": len(results)}


@app.post("/api/social-research/transcribe")
def social_transcribe(req: SRCollectReq):
    _init_social()
    try:
        meta = _collector.collect(req.url)
        if not meta.audio_path:
            raise HTTPException(status_code=404, detail="No se pudo extraer audio")
        result = _transcriber.transcribe(meta.audio_path)
        return {
            "status": "ok",
            "language": result.language,
            "language_probability": result.language_probability,
            "full_text": result.full_text,
            "duration_seconds": result.duration_seconds,
            "segments": [
                {"start": s.start, "end": s.end, "text": s.text, "confidence": s.confidence}
                for s in result.segments
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/social-research/analyze")
def social_analyze(req: SRAnalyzeReq):
    _init_social()
    if req.openai_api_key:
        import openai as openai_mod

        _analyzer.set_client(openai_mod.OpenAI(api_key=req.openai_api_key))
    try:
        col = SocialCollector()
        frames = col.extract_frames(req.video_path, fps=0.15, max_frames=10)
        frame_paths = [f["path"] for f in frames]
        result = _analyzer.analyze_video(
            video_path=req.video_path,
            transcription_text=req.transcription_text,
            visual_samples=frame_paths,
        )
        return {
            "status": "ok",
            "analysis": {
                "topics": [
                    {
                        "topic": t.topic,
                        "category": t.category,
                        "confidence": t.confidence,
                        "keywords": t.keywords,
                    }
                    for t in result.topics
                ],
                "summary": result.summary,
                "visual_description": (
                    result.visual_analysis.description if result.visual_analysis else ""
                ),
                "key_moments": result.key_moments,
                "is_educational": result.is_educational,
                "is_entertainment": result.is_entertainment,
                "educational_score": result.is_educational_score,
                "entertainment_score": result.is_entertainment_score,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/social-research/classify")
def social_classify(req: SRAnalyzeReq):
    _init_social()
    try:
        topics = [t.topic for t in _analyzer._classify_topics(req.transcription_text)]
        visual_desc = ""
        col = SocialCollector()
        frames = (
            col.extract_frames(req.video_path, fps=0.05, max_frames=3) if req.video_path else []
        )
        if frames:
            va = _analyzer.analyze_visual(frames[0]["path"])
            visual_desc = va.description
        importance = _classifier.classify_importance(
            transcription_text=req.transcription_text,
            visual_desc=visual_desc,
            topics=topics,
        )
        tags = _classifier.tag_content(req.transcription_text, topics)
        profile = ContentProfile(
            url=req.video_path,
            platform="unknown",
            title=req.video_path,
            transcription_summary=req.transcription_text[:300],
            topics=topics,
            visual_description=visual_desc,
            importance=importance,
            tags=tags,
            analysis_timestamp=0,
        )
        save = _classifier.auto_save_decision(profile)
        return {
            "status": "ok",
            "importance": {
                "score": importance.score,
                "level": importance.level,
                "reasons": importance.reasons,
            },
            "topics": topics,
            "tags": tags,
            "auto_save": save,
            "visual_description": visual_desc,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/social-research/research")
def social_research(req: SRResearchReq):
    _init_social()
    results = []
    search_queries = [
        f"{req.topic}",
        f"{req.topic} tutorial",
        f"{req.topic} guía",
        f"{req.topic} 2026",
    ]
    for query in search_queries[:3]:
        try:
            from backend.skills.web.search import run as search_skill

            search_result = search_skill({"query": query})
            results.append({"query": query, "result": str(search_result)[:1000]})
        except Exception as e:
            results.append({"query": query, "error": str(e)})
    return {
        "status": "ok",
        "topic": req.topic,
        "queries_executed": len(results),
        "results": results,
        "note": "Investigación inicial ejecutada. Use /collect con URLs encontradas para análisis profundo.",
    }


@app.post("/api/social-research/save")
def social_save(req: SRSaveReq):
    _init_social()
    try:
        profile = ContentProfile(
            url=req.profile.get("url", ""),
            platform=req.profile.get("platform", ""),
            title=req.profile.get("title", ""),
            transcription_summary=req.profile.get("transcription_summary", ""),
            topics=req.profile.get("topics", []),
            visual_description=req.profile.get("visual_description", ""),
            importance=ImportanceScore(
                **req.profile.get("importance", {"score": 0.5, "level": "medium", "reasons": []})
            ),
            tags=req.profile.get("tags", []),
            analysis_timestamp=time.time(),
        )
        saved = _memory_bridge.save_to_memory(
            profile=profile,
            transcription_text=req.transcription_text,
            visual_desc=req.visual_desc,
        )
        return {
            "status": "saved",
            "content_id": saved.content_id,
            "importance": saved.importance_score,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/social-research/library")
def social_library(limit: int = 50, min_importance: Optional[float] = None):
    _init_social()
    items = _memory_bridge.list_all(limit=limit, min_importance=min_importance)
    return {
        "total": len(items),
        "items": [
            {
                "content_id": i.content_id,
                "title": i.title,
                "url": i.url,
                "platform": i.platform,
                "importance_score": i.importance_score,
                "topics": i.topics,
                "tags": i.tags,
                "summary": i.summary,
                "saved_at": i.saved_at,
            }
            for i in items
        ],
    }


@app.get("/api/social-research/library/search")
def social_library_search(q: str, top_k: int = 10):
    _init_social()
    results = _memory_bridge.search_library(q, top_k=top_k)
    return {
        "query": q,
        "results": [
            {
                "content_id": r.content_id,
                "title": r.title,
                "importance_score": r.importance_score,
                "topics": r.topics,
                "summary": r.summary,
            }
            for r in results
        ],
    }


@app.get("/api/social-research/library/stats")
def social_library_stats():
    _init_social()
    return _memory_bridge.get_stats()


@app.post("/api/social-research/deep-research")
def social_deep_research(req: SRResearchReq):
    return social_agent.deep_research(
        topic=req.topic,
        max_sources=req.max_results,
        platforms=req.platforms,
        focus_keywords=req.focus_keywords,
    )


@app.post("/api/proactive/alert")
def proactive_alert(req: dict):
    title = req.get("title", "")
    body = req.get("body", "")
    severity = req.get("severity", "info")
    ttl = int(req.get("ttl", 3600))
    event = proactive.alert(title=title, body=body, severity=severity, ttl_seconds=ttl)
    return JSONResponse(
        {
            "status": "ok",
            "event": {"id": event.id, "title": event.title, "severity": event.severity},
        }
    )


@app.post("/api/proactive/remind")
def proactive_remind(req: dict):
    title = req.get("title", "")
    body = req.get("body", "")
    due_at = req.get("due_at", "")
    repeat = req.get("repeat", "none")
    reminder = proactive.remind(title=title, body=body, due_at=due_at, repeat=repeat)
    return JSONResponse(
        {
            "status": "ok",
            "reminder": {"id": reminder.id, "title": reminder.title, "due_at": reminder.due_at},
        }
    )


@app.post("/api/proactive/owner-state")
def proactive_owner_state(req: dict):
    state = proactive.update_owner_state(
        mood=req.get("mood", ""), focus=req.get("focus", ""), activity=req.get("activity", "")
    )
    return JSONResponse({"status": "ok", "state": state})


@app.get("/api/proactive/alerts")
def proactive_alerts(limit: int = 20):
    return JSONResponse({"alerts": proactive.active_alerts(limit=limit)})


@app.get("/api/proactive/reminders")
def proactive_reminders(limit: int = 20):
    return JSONResponse({"reminders": proactive.due_reminders(limit=limit)})


@app.get("/api/evolution/metrics")
def evolution_metrics(limit: int = 20):
    return JSONResponse({"metrics": evolution.top_skills(limit=limit)})


@app.post("/api/evolution/record")
def evolution_record(req: dict):
    skill = req.get("skill", "")
    success = bool(req.get("success", True))
    latency = float(req.get("latency_ms", 0))
    note = req.get("note", "")
    if not skill:
        return JSONResponse({"status": "error", "error": "skill required"}, status_code=400)
    result = evolution.record(skill=skill, success=success, latency_ms=latency, note=note)
    return JSONResponse({"status": "ok", "metric": result})


@app.post("/api/evolution/evolve")
def evolution_evolve(req: dict):
    skill = req.get("skill", "")
    if not skill:
        return JSONResponse({"status": "error", "error": "skill required"}, status_code=400)
    result = evolution.evolve(skill)
    return JSONResponse(result)


@app.get("/api/learning/rules")
def learning_rules(limit: int = 20):
    return JSONResponse({"rules": compound.active_rules(limit=limit)})


@app.post("/api/learning/record-error")
def learning_record_error(req: dict):
    pattern = req.get("pattern", "")
    context = req.get("context", "")
    if not pattern:
        return JSONResponse({"status": "error", "error": "pattern required"}, status_code=400)
    result = compound.record_error(pattern=pattern, context=context)
    return JSONResponse({"status": "ok", "cluster": result})


@app.post("/api/learning/suppress")
def learning_suppress(req: dict):
    pattern = req.get("pattern", "")
    if not pattern:
        return JSONResponse({"status": "error", "error": "pattern required"}, status_code=400)
    result = compound.suppress(pattern)
    return JSONResponse(result)


@app.get("/")
def index():
    idx = FRONTEND_DIR / "index.html"
    if idx.exists():
        return FileResponse(idx)
    return JSONResponse({"status": "ok", "message": "ARIA App v2.0 running", "docs": "/docs"})


@app.get("/api/plugins")
async def list_plugins():
    return JSONResponse(plugin_manager.list_plugins())


@app.get("/api/plugins/{plugin_name}")
async def get_plugin_info(plugin_name: str):
    plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")
    return plugin_manager.plugin_metadata.get(plugin_name, {})


@app.post("/api/plugins/reload")
async def reload_plugins():
    plugin_manager.plugins = {}
    plugin_manager.hooks = {}
    plugin_manager.plugin_metadata = {}
    plugin_manager.load_all_plugins()
    return {"status": "plugins_reloaded", "count": len(plugin_manager.plugins)}


@app.delete("/api/plugins/{plugin_name}")
async def unload_plugin(plugin_name: str):
    if plugin_manager.unload_plugin(plugin_name):
        return {"status": "plugin_unloaded", "plugin": plugin_name}
    raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")


@app.post("/api/automation/rules")
async def create_automation_rule(rule_data: AutomationRuleModel):
    rule_id = automation_engine.add_rule(rule_data)
    return {"status": "rule_created", "rule_id": rule_id, "rule_name": rule_data.name}


@app.get("/api/automation/rules")
async def list_automation_rules(enabled_only: bool = False, tag: str = None):
    rules = automation_engine.list_rules()
    if enabled_only:
        rules = {k: v for k, v in rules.items() if v["enabled"]}
    if tag:
        rules = {k: v for k, v in rules.items() if tag in v["tags"]}
    return rules


@app.get("/api/automation/rules/{rule_id}")
async def get_automation_rule(rule_id: str):
    rule = automation_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule.to_dict()


@app.put("/api/automation/rules/{rule_id}")
async def update_automation_rule(rule_id: str, rule_data: AutomationRuleModel):
    if automation_engine.update_rule(rule_id, rule_data):
        return {"status": "rule_updated", "rule_id": rule_id}
    raise HTTPException(status_code=404, detail="Rule not found")


@app.delete("/api/automation/rules/{rule_id}")
async def delete_automation_rule(rule_id: str):
    if automation_engine.delete_rule(rule_id):
        return {"status": "rule_deleted", "rule_id": rule_id}
    raise HTTPException(status_code=404, detail="Rule not found")


@app.patch("/api/automation/rules/{rule_id}/enable")
async def enable_automation_rule(rule_id: str, enabled: bool):
    if automation_engine.enable_rule(rule_id, enabled):
        return {"status": f"rule_{('enabled' if enabled else 'disabled')}", "rule_id": rule_id}
    raise HTTPException(status_code=404, detail="Rule not found")


@app.post("/api/automation/test/{rule_id}")
async def test_automation_rule(rule_id: str):
    rule = automation_engine.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    success = await automation_engine.execute_rule(rule)
    return {
        "status": "executed",
        "success": success,
        "rule_id": rule_id,
        "execution_count": rule.execution_count,
        "last_error": rule.last_error,
    }


@app.post("/api/automation/monitor/start")
async def start_automation_monitor():
    if not automation_engine.monitoring:
        asyncio.create_task(automation_engine.start_monitoring())
        return {"status": "monitoring_started"}
    return {"status": "already_monitoring"}


@app.post("/api/automation/monitor/stop")
async def stop_automation_monitor():
    automation_engine.stop_monitoring()
    return {"status": "monitoring_stopped"}


@app.get("/api/automation/monitor/status")
async def automation_monitor_status():
    return {
        "monitoring": automation_engine.monitoring,
        "rules_count": len(automation_engine.rules),
        "interval": automation_engine.monitor_interval,
    }


@app.post("/api/agents/kilo/delegate", tags=["Kilo Agent"])
async def delegate_to_kilo(task: KiloTask):
    return await kilo_bridge.delegate_task(task)


@app.post("/api/agents/kilo/callback", tags=["Kilo Agent"])
async def kilo_callback(task_id: str, result: dict):
    await kilo_bridge.handle_callback(task_id, result)
    return {"status": "received"}


@app.get("/api/agents/kilo/status/{task_id}", tags=["Kilo Agent"])
async def kilo_task_status(task_id: str):
    return kilo_bridge.get_task_status(task_id)


@app.get("/api/agents/kilo/history", tags=["Kilo Agent"])
async def kilo_history(limit: int = 50):
    return kilo_bridge.get_history(limit)


# =============================================================================
# Mobile Sync
# =============================================================================


@app.post("/api/mobile/discovery", tags=["Mobile"])
async def mobile_discovery():
    """Endpoint de descubrimiento para clientes moviles."""
    return {
        "name": "ARIA OS",
        "version": "2.0.0",
        "port": 8000,
        "api_version": "v2",
        "features": [
            "chat",
            "skills",
            "voice",
            "auth",
            "sync",
            "social-research",
            "video-analysis",
        ],
        "status": "online",
    }


# =============================================================================
# ARIA Visual + Observer Endpoints
# =============================================================================


class AriaChatRequest(BaseModel):
    message: str


class AriaLearnRequest(BaseModel):
    user_input: str
    feedback: str


class G7StartRequest(BaseModel):
    backend_url: str = "http://localhost:8000"


class G7SuggestionsRequest(BaseModel):
    count: int = 3


class G7AcceptRequest(BaseModel):
    suggestion_id: str


class G7RejectRequest(BaseModel):
    suggestion_id: str


@app.get("/api/aria/health")
def aria_health():
    return JSONResponse(
        {
            "status": "ok",
            "engine": "running" if ARIA_ENGINE_ENABLED else "disabled",
            "observer": "running" if ARIA_ENABLED else "disabled",
            "timestamp": time.time(),
        }
    )


@app.post("/api/aria/chat")
async def aria_chat(req: AriaChatRequest):
    text = (req.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="message vacío")

    if aria_engine and ARIA_ENGINE_ENABLED:
        loop = asyncio.get_event_loop()
        cached = _get_cached_context()
        if cached:
            context = cached
        else:
            context = await loop.run_in_executor(
                None, aria_observer.build_context
            ) if ARIA_ENABLED else {}
            _cache_context(context)
        try:
            result = await aria_engine.generate_response(text, context)
            response_text = result.get("response", "")
            tool_results = []
            if aria_engine.tool_registry.has_tools_in_text(response_text):
                cleaned, results = await loop.run_in_executor(
                    None, aria_engine.process_with_tools, response_text, context)
                response_text = cleaned
                tool_results = results
            return JSONResponse(
                {
                    "response": response_text,
                    "suggestions": result.get("suggested_actions", []),
                    "state": result.get("state", "active"),
                    "pattern": result.get("pattern_detected", {}),
                    "tool_results": tool_results,
                    "tool_stats": aria_engine.get_tool_stats(),
                }
            )
        except Exception as exc:
            return JSONResponse(
                {
                    "response": f"[ARIA] Error al procesar: {str(exc)[:200]}",
                    "suggestions": [],
                    "state": "idle",
                }
            )

    return JSONResponse(
        {
            "response": f"Recibido: {text[:100]}",
            "suggestions": [],
            "state": "idle",
        }
    )

# ARIA USB & ADAPTIVE ENDPOINTS (v4.0)

@app.get("/api/aria/usb/status")
async def get_usb_status():
    """Estado de USBs conectados"""
    if USB_INTELLIGENCE_ENABLED:
        return await handle_usb_status()
    return {"usb_count": 0, "devices": [], "error": "USB intelligence not available"}

@app.get("/api/aria/usb/expand")
async def expand_with_usb():
    """Expande ARIA con contenido del USB"""
    if USB_INTELLIGENCE_ENABLED:
        return await handle_usb_expansion()
    return {"error": "USB intelligence not available"}

@app.post("/api/aria/auto")
async def aria_intelligent_auto(req: dict):
    """ARIA automatica e inteligente (sin scripts)"""
    message = req.get("message", "")
    context = req.get("context")
    if USB_INTELLIGENCE_ENABLED:
        return await handle_aria_auto(message, context)
    return {"status": "error", "message": "Adaptive engine not available"}

@app.get("/api/aria/profile")
def aria_profile():
    if aria_engine and ARIA_ENGINE_ENABLED:
        stats = aria_engine.get_stats()
        stats["tool_stats"] = aria_engine.get_tool_stats()
        stats["safety_patterns"] = get_blocked_patterns_count() if ARIA_SAFETY_ENABLED else 0
        return JSONResponse(stats)
    return JSONResponse({"total_interactions": 0, "interests_count": 0})


@app.post("/api/aria/safety/check")
def aria_safety_check(req: dict):
    command = req.get("command", "")
    if not command:
        return JSONResponse({"error": "command required"}, status_code=400)
    if aria_engine and ARIA_ENGINE_ENABLED and ARIA_SAFETY_ENABLED:
        result = aria_engine.safety_check_command(command)
    else:
        from backend.safety_filter import safety_check
        result = safety_check(command)
    return JSONResponse(result)


@app.post("/api/aria/learn")
async def aria_learn(req: AriaLearnRequest):
    if aria_engine and ARIA_ENGINE_ENABLED:
        try:
            result = await aria_engine.learn_from_interaction(req.user_input, req.feedback)
            return JSONResponse(result)
        except Exception as exc:
            return JSONResponse({"status": "error", "error": str(exc)})
    return JSONResponse({"status": "disabled"})


@app.websocket("/api/aria/observe")
async def aria_observe(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "context_request":
                    context = aria_observer.build_context() if ARIA_ENABLED else {}
                    await websocket.send_json(
                        {
                            "activity": context.get("current_app", "idle"),
                            "status": "active",
                            "context": context,
                            "timestamp": time.time(),
                        }
                    )
                elif msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})
                else:
                    await websocket.send_json({"status": "ok"})
            except json.JSONDecodeError:
                await websocket.send_json({"status": "ok"})
    except WebSocketDisconnect:
        pass


@app.get("/aria_widget.html")
def aria_widget():
    path = APP_DIR / "frontend" / "aria_widget.html"
    if path.exists():
        return FileResponse(path, media_type="text/html")
    return JSONResponse({"error": "widget not found"}, status_code=404)


@app.get("/aria_dashboard_v3.html")
def aria_dashboard_v3():
    path = APP_DIR / "frontend" / "aria_dashboard_v3.html"
    if path.exists():
        return FileResponse(path, media_type="text/html")
    return JSONResponse({"error": "dashboard not found"}, status_code=404)


@app.get("/aria_core.js")
def aria_core_js():
    path = APP_DIR / "frontend" / "aria_core.js"
    if path.exists():
        return FileResponse(path, media_type="application/javascript")
    return JSONResponse({"error": "not found"}, status_code=404)


# =============================================================================
# ARIA Content Generation Endpoints
# =============================================================================


class StoryGenRequest(BaseModel):
    prompt: str
    length: str = "medium"
    context_aware: bool = True


class CharacterGenRequest(BaseModel):
    role: str = "hero"
    traits: List[str] = None


class WorldGenRequest(BaseModel):
    theme: str = "fantasy"
    size: str = "medium"


class PromptGenRequest(BaseModel):
    description: str
    style: str = "anime"


class InteractiveStoryRequest(BaseModel):
    scene: str
    story_id: str = "default"
    branches: int = 4


class LoraTrainRequest(BaseModel):
    dataset_path: str
    num_epochs: int = 3
    lora_rank: int = 8
    lora_alpha: int = 16


class DatasetCreateRequest(BaseModel):
    pass


@app.post("/api/aria/generate/story")
async def generate_story(req: StoryGenRequest):
    if not GENERATION_ENABLED or not story_gen:
        return JSONResponse({"error": "Content generation not available"}, status_code=503)
    try:
        context = None
        if req.context_aware and aria_observer:
            context = aria_observer.build_context()
        result = await story_gen.generate_story(req.prompt, req.length, context)
        saved = content_lib.save(
            "story",
            result.get("story", "")[:500],
            {
                "title": result.get("title"),
                "length": req.length,
            },
            context=json.dumps(context) if context else "",
        )
        result["saved_id"] = saved
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/aria/generate/character")
async def generate_character(req: CharacterGenRequest):
    if not GENERATION_ENABLED or not char_designer:
        return JSONResponse({"error": "Content generation not available"}, status_code=503)
    try:
        traits = req.traits or ["strong", "unique"]
        result = await char_designer.design_character(role=req.role, traits=traits)
        saved = content_lib.save(
            "character", json.dumps(result), {"role": req.role, "traits": traits}
        )
        result["saved_id"] = saved
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/aria/generate/world")
async def generate_world(req: WorldGenRequest):
    if not GENERATION_ENABLED or not world_builder:
        return JSONResponse({"error": "Content generation not available"}, status_code=503)
    try:
        result = await world_builder.build_world(req.theme, req.size)
        saved = content_lib.save(
            "world", json.dumps(result), {"theme": req.theme, "size": req.size}
        )
        result["saved_id"] = saved
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/aria/generate/prompt")
async def generate_prompt(req: PromptGenRequest):
    if not GENERATION_ENABLED or not prompt_opt:
        return JSONResponse({"error": "Content generation not available"}, status_code=503)
    try:
        result = await prompt_opt.optimize_for_art(req.description, req.style)
        saved = content_lib.save(
            "prompt", req.description, {"style": req.style, "optimized": result["prompt"]}
        )
        result["saved_id"] = saved
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/aria/content/interactive")
async def interactive_story(req: InteractiveStoryRequest):
    if not GENERATION_ENABLED or not aria_content_engine:
        return JSONResponse({"error": "Content generation not available"}, status_code=503)
    try:
        result = await aria_content_engine.generate_interactive_story(req.scene, req.story_id)
        result["branches_requested"] = req.branches
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/aria/content/suggest")
async def content_suggest(context_req: dict = None):
    if not GENERATION_ENABLED or not aria_content_engine:
        return JSONResponse({"error": "Content generation not available"}, status_code=503)
    try:
        context = context_req or {}
        if aria_observer and not context:
            context = aria_observer.build_context()
        result = await aria_content_engine.suggest_content(context)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/aria/content/personalize")
async def personalize_content(personalize_req: dict = None):
    if not GENERATION_ENABLED or not aria_content_engine:
        return JSONResponse({"error": "Content generation not available"}, status_code=503)
    try:
        content = personalize_req.get("content", "") if personalize_req else ""
        profile = personalize_req.get("profile", {}) if personalize_req else {}
        if not content:
            return JSONResponse({"error": "content required"}, status_code=400)
        result = await aria_content_engine.personalize_content(content, profile)
        return JSONResponse({"personalized": result})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# Dataset endpoints
@app.post("/api/aria/dataset/create")
async def create_dataset(req: DatasetCreateRequest = None):
    if not ML_ENABLED or not dataset_builder:
        return JSONResponse({"error": "Dataset builder not available"}, status_code=503)
    try:
        result = await dataset_builder.create_training_set()
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/aria/dataset/validate")
async def validate_dataset(req: DatasetCreateRequest = None):
    if not ML_ENABLED or not dataset_builder:
        return JSONResponse({"error": "Dataset builder not available"}, status_code=503)
    try:
        result = await dataset_builder.validate_dataset()
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# LoRA endpoints
@app.post("/api/aria/lora/train")
async def train_lora(req: LoraTrainRequest):
    if not LORA_ENABLED or not lora_trainer:
        return JSONResponse({"error": "LoRA trainer not available"}, status_code=503)
    try:
        result = await lora_trainer.train_lora(
            req.dataset_path, req.num_epochs, req.lora_rank, req.lora_alpha
        )
        return JSONResponse(
            {
                "status": result.status,
                "loss_curve": [
                    {"epoch": p.epoch, "step": p.step, "loss": p.loss, "perplexity": p.perplexity}
                    for p in result.loss_curve
                ],
                "time_taken": result.time_taken,
                "final_loss": result.final_loss,
                "model_name": result.model_name,
            }
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/aria/lora/merge")
async def merge_lora():
    if not LORA_ENABLED or not lora_trainer:
        return JSONResponse({"error": "LoRA trainer not available"}, status_code=503)
    try:
        result = await lora_trainer.create_merged_model()
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/aria/lora/test")
async def test_lora():
    if not LORA_ENABLED or not lora_trainer:
        return JSONResponse({"error": "LoRA trainer not available"}, status_code=503)
    try:
        result = await lora_trainer.test_great_sage()
        return JSONResponse(
            {
                "before": result.before,
                "after": result.after,
                "improvement_score": result.improvement_score,
            }
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# Content library endpoints
@app.get("/api/aria/content/library")
def content_library(type_: str = None, limit: int = 20, sort_by: str = "recent"):
    if not content_lib:
        return JSONResponse({"error": "Content library not available"}, status_code=503)
    try:
        items = content_lib.get_library(type_=type_, limit=limit, sort_by=sort_by)
        return JSONResponse({"total": len(items), "items": items})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/aria/content/rate")
async def rate_content(req: dict = None):
    if not content_lib:
        return JSONResponse({"error": "Content library not available"}, status_code=503)
    try:
        item_id = (req or {}).get("id", 0)
        rating = (req or {}).get("rating", 0)
        success = content_lib.rate(item_id, rating)
        return JSONResponse({"status": "rated" if success else "failed"})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# Test endpoints
@app.post("/api/aria/test/run")
async def run_tests():
    try:
        from backend.tests.test_great_sage import TestGreatSage

        tester = TestGreatSage()
        results = tester.run_all()
        return JSONResponse(results)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# =============================================================================
# G7 Integration — Import
# =============================================================================

try:
    from backend.aria_integration import AriaIntegration

    aria_integration = AriaIntegration()
    G7_ENABLED = True
except Exception:
    aria_integration = None
    G7_ENABLED = False


# =============================================================================
# G7 Integration Endpoints
# =============================================================================


@app.post("/api/aria/g7/start")
async def g7_start(req: G7StartRequest = None):
    if not G7_ENABLED or not aria_integration:
        return JSONResponse({"error": "G7 integration not available"}, status_code=503)
    try:
        url = req.backend_url if req and req.backend_url else "http://localhost:8000"
        if req:
            aria_integration.backend_url = url
        result = await aria_integration.start_full_aria()
        return JSONResponse({"status": "started", **result})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/aria/g7/suggestions")
async def g7_suggestions(count: int = 3):
    if not G7_ENABLED or not aria_integration:
        return JSONResponse({"error": "G7 integration not available"}, status_code=503)
    try:
        suggestions = await aria_integration.get_suggestions(count=count)
        return JSONResponse({"suggestions": suggestions, "count": len(suggestions)})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/aria/g7/suggestions/accept")
async def g7_accept(req: G7AcceptRequest):
    if not G7_ENABLED or not aria_integration:
        return JSONResponse({"error": "G7 integration not available"}, status_code=503)
    try:
        result = await aria_integration.accept_suggestion(req.suggestion_id)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/aria/g7/suggestions/reject")
async def g7_reject(req: G7RejectRequest):
    if not G7_ENABLED or not aria_integration:
        return JSONResponse({"error": "G7 integration not available"}, status_code=503)
    try:
        result = await aria_integration.reject_suggestion(req.suggestion_id)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.websocket("/api/aria/g7/stream")
async def g7_stream(websocket: WebSocket):
    if not G7_ENABLED or not aria_integration:
        await websocket.close(code=1000, reason="G7 not available")
        return
    await websocket.accept()
    try:
        await aria_integration.websocket_handler(websocket)
    except Exception:
        pass
    finally:
        try:
            websocket.close()
        except Exception:
            pass


# =============================================================================
# PHASE I — Enhanced Dashboard + Monitoring + Privacy
# =============================================================================

try:
    from backend.monitoring.screen_analyzer import ScreenAnalyzer

    SCREEN_ANALYZER = ScreenAnalyzer()
    SCREEN_AVAILABLE = True
except Exception:
    SCREEN_ANALYZER = None
    SCREEN_AVAILABLE = False

try:
    from backend.monitoring.audio_analyzer import AudioAnalyzer

    AUDIO_ANALYZER = AudioAnalyzer()
    AUDIO_AVAILABLE = True
except Exception:
    AUDIO_ANALYZER = None
    AUDIO_AVAILABLE = False

try:
    from backend.monitoring.contextual_engine import ContextualUnderstandingEngine

    CONTEXTUAL_ENGINE = ContextualUnderstandingEngine()
    CONTEXTUAL_AVAILABLE = True
except Exception:
    CONTEXTUAL_ENGINE = None
    CONTEXTUAL_AVAILABLE = False

try:
    from backend.monitoring.background_learning import BackgroundLearningDaemon

    BG_LEARNING = BackgroundLearningDaemon()
    BG_LEARNING_AVAILABLE = True
except Exception:
    BG_LEARNING = None
    BG_LEARNING_AVAILABLE = False

try:
    from backend.security.privacy_filter import PrivacyFilter

    PRIVACY_FILTER = PrivacyFilter()
    PRIVACY_AVAILABLE = True
except Exception:
    PRIVACY_FILTER = None
    PRIVACY_AVAILABLE = False

try:
    from backend.system_integration import SystemIntegration

    SYSTEM_INTEGRATION = SystemIntegration()
    SYSTEM_AVAILABLE = True
except Exception:
    SYSTEM_INTEGRATION = None
    SYSTEM_AVAILABLE = False


class FloatingStatusRequest(BaseModel):
    visible: Optional[bool] = None


class AudioAnalyzeRequest(BaseModel):
    action: Optional[str] = None


@app.get("/aria_dashboard_v4.html")
def aria_dashboard_v4():
    path = APP_DIR / "frontend" / "aria_dashboard_v4.html"
    if path.exists():
        return FileResponse(path, media_type="text/html")
    return JSONResponse({"error": "dashboard not found"}, status_code=404)


@app.get("/api/aria/floating/status")
def floating_status():
    status = {
        "visible": True,
        "invisible_mode": False,
        "platform": SYSTEM_INTEGRATION.get_platform() if SYSTEM_INTEGRATION else "unknown",
        "widget_position": {"x": 0, "y": 0, "width": 300, "height": 300},
        "z_index": 999999,
        "tray_available": SYSTEM_INTEGRATION is not None,
    }
    if SYSTEM_INTEGRATION:
        try:
            info = SYSTEM_INTEGRATION.get_system_info()
            status["system_info"] = info
        except Exception:
            pass
    return JSONResponse(status)


@app.post("/api/aria/floating/mode")
async def floating_mode(req: FloatingStatusRequest):
    if SYSTEM_INTEGRATION and req.visible is not None:
        try:
            if req.visible:
                SYSTEM_INTEGRATION.create_floating_window()
            else:
                SYSTEM_INTEGRATION.create_tray_icon()
        except Exception:
            pass
    return JSONResponse({"visible": req.visible, "status": "ok"})


@app.get("/api/aria/context/understand")
async def context_understand():
    if CONTEXTUAL_AVAILABLE and CONTEXTUAL_ENGINE:
        try:
            state = await CONTEXTUAL_ENGINE.understand_current_state()
            prediction = await CONTEXTUAL_ENGINE.predict_next_action()
            return JSONResponse(
                {
                    "state": state.state,
                    "confidence": state.confidence,
                    "intent": state.intent,
                    "mood": state.mood,
                    "active_app": state.active_app,
                    "suggestions": state.suggestions,
                    "prediction": prediction.get("prediction", ""),
                    "prediction_confidence": prediction.get("confidence", 0),
                }
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse({"state": "initializing", "confidence": 0.1, "intent": "general"})


@app.get("/api/aria/predict")
async def predict_next():
    if CONTEXTUAL_AVAILABLE and CONTEXTUAL_ENGINE:
        try:
            prediction = await CONTEXTUAL_ENGINE.predict_next_action()
            return JSONResponse(prediction)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse({"prediction": "Continue current activity", "confidence": 0.3})


@app.get("/api/aria/audio/analyze")
async def audio_analyze():
    if AUDIO_AVAILABLE and AUDIO_ANALYZER:
        try:
            activity = await AUDIO_ANALYZER.detect_audio_activity()
            ambient = await AUDIO_ANALYZER.ambient_sound_analysis()
            return JSONResponse(
                {
                    "audio_detected": activity.get("audio_detected"),
                    "volume": activity.get("volume"),
                    "ambient_type": ambient.get("ambient_type"),
                    "quietness": ambient.get("quietness_score"),
                }
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse({"audio_detected": False, "volume": 0})


@app.post("/api/aria/audio/recognize")
async def audio_recognize():
    if AUDIO_AVAILABLE and AUDIO_ANALYZER:
        try:
            speech = await AUDIO_ANALYZER.speech_recognition()
            return JSONResponse(speech)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse({"speech": "", "confidence": 0, "is_command": False})


@app.get("/api/aria/privacy/report")
async def privacy_report():
    if PRIVACY_AVAILABLE and PRIVACY_FILTER:
        try:
            report = await PRIVACY_FILTER.user_transparency()
            score = PRIVACY_FILTER.get_privacy_score()
            report["privacy_score"] = score
            return JSONResponse(report)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse(
        {
            "report": {"privacy_score": 100.0, "total_processed": 0, "total_filtered": 0},
            "privacy_score": 100.0,
        }
    )


@app.get("/api/connectors/health")
async def connectors_health() -> JSONResponse:
    connectors = {}
    for name in [
        "notion",
        "slack",
        "google",
        "discord",
        "twitter",
        "supabase",
        "stripe",
        "stable_diffusion",
        "github",
        "huggingface",
    ]:
        try:
            mod = __import__(f"backend.connectors.{name}_connector", fromlist=[name])
            cls = getattr(mod, f"{name.replace('_', '').title().replace(' ', '')}Connector")
            conn = cls()
            connectors[name] = {"available": True, "connected": conn.is_available}
        except Exception:
            connectors[name] = {"available": False, "connected": False}
    return JSONResponse({"connectors": connectors, "total": len(connectors)})


@app.post("/api/aria/think")
async def aria_think(request: dict) -> JSONResponse:
    try:
        from backend.aria_brain import AriaBrain

        brain = AriaBrain()
        situation = request.get("situation", "") if isinstance(request, dict) else ""
        options = request.get("options", None) if isinstance(request, dict) else None
        result = await brain.think_and_decide(situation, options)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"decision": "proceed", "confidence": 0.5, "explanation": str(exc)})


@app.get("/api/aria/memory/{query}")
async def aria_memory_query(query: str) -> JSONResponse:
    try:
        from backend.aria_brain import AriaBrain

        brain = AriaBrain()
        result = await brain.query_memory(query)
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)})


@app.get("/api/metrics")
async def metrics() -> JSONResponse:
    try:
        from backend.observability.metrics_collector import MetricsCollector

        collector = MetricsCollector()
        return JSONResponse(await collector.get_all_metrics())
    except Exception as exc:
        return JSONResponse({"error": str(exc)})


@app.get("/api/status/detailed")
async def status_detailed() -> JSONResponse:
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/aria/health", timeout=5) as r:
            health = json.loads(r.read().decode("utf-8"))
    except Exception:
        health = {"status": "degraded"}
    return JSONResponse({**health, "detailed": True, "version": "3.2.0"})


# =============================================================================
# PHASE I ENHANCED — PRO Monitoring Modules
# =============================================================================

try:
    from backend.monitoring.screen_analyzer_pro import (
        capture_screen_optimized,
        detect_visual_changes_fast,
        extract_text_ocr_advanced,
        semantic_understanding_advanced,
    )

    SCREEN_PRO = True
except Exception:
    SCREEN_PRO = False

try:
    from backend.monitoring.audio_analyzer_pro import (
        detect_audio_advanced,
        music_analysis,
        speech_recognition_streaming,
    )

    AUDIO_PRO = True
except Exception:
    AUDIO_PRO = False

try:
    from backend.monitoring.contextual_engine_pro import ContextualEngineAdvanced

    CONTEXT_PRO = True
except Exception:
    CONTEXT_PRO = False

try:
    from backend.monitoring.background_learning_pro import BackgroundLearningDaemon

    BG_LEARNING_PRO = True
except Exception:
    BG_LEARNING_PRO = False

try:
    from backend.system.invisible_mode import AuraInvisibleMode

    INVISIBLE_MODE = True
except Exception:
    INVISIBLE_MODE = False


class ScreenCaptureRequest(BaseModel):
    region: Optional[List[int]] = None


class AudioCaptureRequest(BaseModel):
    duration_ms: int = 500


invisible_mode_instance = AuraInvisibleMode() if INVISIBLE_MODE else None


@app.get("/aria_dashboard_v5_extreme.html")
def aria_dashboard_v5_extreme():
    path = APP_DIR / "frontend" / "aria_dashboard_v5_extreme.html"
    if path.exists():
        return FileResponse(path, media_type="text/html")
    return JSONResponse({"error": "dashboard not found"}, status_code=404)


@app.get("/aria_core_extreme.js")
def aria_core_extreme_js():
    path = APP_DIR / "frontend" / "aria_core_extreme.js"
    if path.exists():
        return FileResponse(path, media_type="application/javascript")
    return JSONResponse({"error": "not found"}, status_code=404)


@app.post("/api/pro/capture")
async def pro_capture(req: ScreenCaptureRequest = None):
    if not SCREEN_PRO:
        return JSONResponse({"error": "Screen capture PRO not available"}, status_code=503)
    try:
        region = tuple(req.region) if req and req.region else None
        result = await capture_screen_optimized(region=region)
        ocr = await extract_text_ocr_advanced(result.image) if result.image else {"text": ""}
        changes = await detect_visual_changes_fast(result.image)
        semantic = await semantic_understanding_advanced(
            image=result.image,
            ocr_text=ocr.get("text", ""),
            active_app=result.active_app,
        )
        return JSONResponse(
            {
                "timestamp": result.timestamp,
                "active_app": result.active_app,
                "ocr": ocr,
                "changes": {
                    "changed": changes.get("changed", False),
                    "regions": changes.get("regions", []),
                    "intensity": changes.get("intensity", 0.0),
                },
                "semantic": semantic,
            }
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/pro/audio/analyze")
async def pro_audio_analyze(req: AudioCaptureRequest = None):
    if not AUDIO_PRO:
        return JSONResponse({"error": "Audio PRO not available"}, status_code=503)
    try:
        audio = await detect_audio_advanced(duration_ms=(req.duration_ms if req else 500))
        speech = await speech_recognition_streaming()
        music = await music_analysis()
        return JSONResponse(
            {
                "audio_detected": audio.audio_detected,
                "volume": audio.volume,
                "type": audio.type,
                "bpm": audio.beats_per_minute,
                "frequency_bands": audio.frequency_bands,
                "speech": speech.transcription,
                "speech_confidence": speech.speech_confidence,
                "speech_language": speech.language,
                "is_command": speech.is_command,
                "music_genre": music.genre,
                "music_bpm": music.bpm,
                "music_mood": music.mood,
            }
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/pro/context/understand")
async def pro_context_understand():
    if not CONTEXT_PRO:
        return JSONResponse({"error": "Context PRO not available"}, status_code=503)
    try:
        engine = ContextualEngineAdvanced()
        state = await engine.understand_current_state_advanced()
        suggestions = await engine.proactive_suggestions()
        emotional = await engine.emotional_tone_detection()
        return JSONResponse(
            {
                "state": state.state,
                "confidence": state.confidence,
                "activity_type": state.activity_type,
                "mood": state.mood,
                "intent": state.intent,
                "emotional_tone": emotional.tone,
                "emotional_intensity": emotional.intensity,
                "suggestions": [
                    {
                        "prediction": s.prediction,
                        "confidence": s.confidence,
                        "action": s.suggested_action,
                    }
                    for s in suggestions
                ],
                "predicted_next_actions": state.predicted_next_actions,
                "session_duration": state.session_duration,
            }
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/pro/learning/patterns")
async def pro_learning_patterns():
    if not BG_LEARNING_PRO:
        return JSONResponse({"error": "Learning PRO not available"}, status_code=503)
    try:
        daemon = BackgroundLearningDaemon()
        patterns = await daemon.pattern_mining()
        predictions = await daemon.predictive_model()
        return JSONResponse(
            {
                "patterns": [
                    {
                        "description": p.description,
                        "frequency": p.frequency,
                        "next_action": p.next_action,
                        "confidence": p.confidence,
                    }
                    for p in patterns
                ],
                "predictions": [
                    {"action": p.action, "probability": p.probability, "context": p.context}
                    for p in predictions
                ],
            }
        )
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/pro/invisible/toggle")
async def pro_invisible_toggle():
    if not INVISIBLE_MODE or not invisible_mode_instance:
        return JSONResponse({"error": "Invisible mode not available"}, status_code=503)
    try:
        result = await invisible_mode_instance.toggle_invisible_mode()
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/pro/invisible/status")
async def pro_invisible_status():
    if not INVISIBLE_MODE or not invisible_mode_instance:
        return JSONResponse({"error": "Invisible mode not available"}, status_code=503)
    return JSONResponse(invisible_mode_instance.get_status())


@app.post("/api/pro/continuous_optimize")
async def pro_continuous_optimize():
    if not BG_LEARNING_PRO:
        return JSONResponse({"error": "Learning PRO not available"}, status_code=503)
    try:
        daemon = BackgroundLearningDaemon()
        return JSONResponse(await daemon.continuous_optimization())
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
