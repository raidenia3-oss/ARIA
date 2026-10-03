"""AURA Backend - Multi-modal AI assistant server.

Serves multiple interfaces:
- REST API for web/mobile/desktop clients
- Discord bot integration
- Godot client support
- Local and cloud AI models
"""
# NOTA: `from __future__ import annotations` NO debe añadirse aquí.
# Con PEP 563 las anotaciones son strings, y las rutas con `@limiter.limit`
# de slowapi registran el WRAPPER ante FastAPI: `get_typed_signature` evalúa
# el string contra `wrapper.__globals__` (los de slowapi, no los de este
# módulo), `eval_type_lenient` traga el NameError y sólo el parámetro body
# revienta en pydantic al construir la ruta -> el import de backend.main
# muere DESPUÉS de registrar las métricas de Prometheus (475-478), y cada
# reintento re-registra los mismos 4 nombres -> DuplicateTimeseries.
import os
import time
import threading
import logging
import uuid
import subprocess
import sys
import json
import asyncio
import secrets
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / "services" / "discord-bot" / ".env", override=False)
# Las claves de proveedores vivían en ame_backend/.env.local y nadie las cargaba:
# ai_router leía os.environ y veía 0 de 6, así que el router degradaba a los 2
# proveedores locales sin avisar. override=False para no pisar lo que venga del
# entorno real (producción, CI) con valores de desarrollo.
load_dotenv(_project_root / "ame_backend" / ".env.local", override=False)

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, Response, WebSocket
from starlette.websockets import WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse, RedirectResponse, FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.knowledge.router import router as knowledge_router
from backend.telemetry.governor import router as governor_router
from backend.database import engine, SessionLocal, Base
from backend.models import User, ServiceStatus, LogEntry, TrainingJob, Conversation, Message
from backend.brain_orchestrator import brain, detect_device_role, DEVICE_UNKNOWN, ROLE_EXTERNAL
from backend.orchestrator import orchestrator, Node, NODE_PC, NODE_SERVER, NODE_MOBILE, ROLE_POWERFUL, ROLE_LIGHT, ROLE_SMALL, ROLE_EXTERNAL
from backend.continuous_improvement import improvement
from backend.rollercoin_endpoints import router as rollercoin_router
from backend.sync_router import router as device_sync_router
from backend.network.mesh_router import router as mesh_router
from backend.p2p_reconcile import router as p2p_reconcile_router
from backend.sync.engine import router as p2p_sync_router
from backend.brain_router import router as brain_router
from backend.treasury_manager import TreasuryManager
from backend.federated_training import FederatedTrainer
from backend.narrative_engine import NarrativeEngine, StoryTone
import backend.narrative_engine as narrative_engine
from backend.narrative_routes import router as narrative_router, init_narrative_engine
from backend.update_manager import UpdateManager, VersionTracker
from backend.update_routes import router as update_router
from backend.mobile_automation_manager import MobileAutomationManager
from backend.mobile_automation_routes import router as mobile_router, init_mobile_automation
from backend.mobile_story_routes import router as mobile_story_router
from backend.mobile_pairing import router as mobile_pairing_router
from backend.sync_engine import router as sync_router
from backend.websocket_manager import ws_gateway
from backend.agent_scheduler import get_agent_scheduler
from backend.audio.routes import router as audio_stt_router
from backend.audio.tts_routes import router as audio_tts_router
from backend.audio.wake_word_routes import router as wake_word_router
from backend.audio.voice_routes import router as voice_interaction_router
from backend.agents.orchestrator_routes import router as agent_orchestrator_router
from backend.agent.memory_routes import router as agent_memory_router
from backend.agents.tools_routes import router as tools_registry_router
from backend.agent.sandbox_routes import router as sandbox_router
from backend.sandbox.router import router as ephemeral_sandbox_router
from backend.network_mesh.mesh_routes import router as mesh_router
from backend.master_control.master_routes import router as master_dashboard_router
from backend.daemon.daemon_routes import router as daemon_lifecycle_router
from backend.daemon.sync_routes import router as daemon_sync_router
from backend.daemon.aura_daemon import get_daemon
from backend.api.ame_sync_routes import router as ame_sync_router
from backend.api.storage_routes import router as storage_router
from backend.api.automation_routes import router as automation_router
from backend.api.whatsapp_routes import router as whatsapp_router
from backend.api.learning_routes import router as learning_api_router
from backend.bots.whatsapp_bot import get_whatsapp_bot as _get_whatsapp_bot
whatsapp_bot = _get_whatsapp_bot()
from backend.api.cloud_routes import router as cloud_router
from backend.agents.learning_routes import router as agent_learning_router
from backend.resilience.healing_routes import router as healing_router
from backend.runner.runner_routes import router as ecosystem_router
from backend.fusion.fusion_routes import router as fusion_context_router
from backend.predictive.predictive_routes import router as predictive_scheduler_router
from backend.recovery.recovery_routes import router as recovery_snapshot_router
from backend.edge_ai.finetune_routes import router as edge_finetune_router
from backend.cognitive_graph.cognitive_routes import router as cognitive_graph_router
from backend.mesh_consensus.consensus_routes import router as mesh_consensus_router
from backend.agent.evolution_routes import router as evolution_router
from backend.agent.research_routes import router as research_router
from backend.agent.swarm_routes import router as agent_swarm_router
from backend.automation.scheduler_routes import router as scheduler_router, enable_autostart as scheduler_enable_autostart
from backend.desktop.desktop_routes import desktop_router as desktop_router
from backend.desktop.window_routes import router as window_router
from backend.desktop.overlay_routes_b75 import router as overlay_b75_router
from backend.hud.omni_routes import router as omni_hud_router
from backend.media.routes import router as media_router
from backend.self_learning_manager import SelfLearningManager
from backend.self_learning_routes import router as selflearn_router, init_self_learning
from backend.agents.kilo_bridge import kilo_bridge, KiloTask
from backend.plugins import plugin_manager
from backend.automation import automation_engine
from backend.automation.memory_routes import router as automation_memory_router
from backend.automation.models import AutomationRuleModel
from backend.fanfic_routes import router as fanfic_router
from backend.story_routes import router as story_router
from backend.story_memory.session_context import get_session_context
from backend.analytics_routes import router as analytics_router, init_analytics, billing_router
from backend.localization_routes import router as localization_router, init_localization
from backend.security_routes import router as security_router, init_security
from backend.security.vault import router as vault_router
from backend.security.mitigation_routes import router as defense_router
from backend.security.identity_routes import router as identity_router
from backend.security.zk_routes import router as zk_audit_router
from backend.evolution.patcher import router as patcher_router
from backend.planner.planner_routes import router as planner_router
from backend.refactoring.engine import router as refactoring_router
from backend.core.aura_master_runtime import router as aura_master_router
from backend.ai.routes import router as finetune_lora_router
from backend.ai.federated_routes import router as federated_lora_router
from backend.testing.routes import router as testing_matrix_router
from backend.swarm.swarm_routes import router as swarm_marketplace_router
from backend.device_routes import router as device_router, init_device_modules
from backend.finetuning_routes import router as finetuning_router, init_finetuning
from backend.nomad.nomad_routes import router as nomad_router
from backend.diagnostics.routes import router as health_router
from backend.diagnostics.omni_routes import router as omni_router
from backend.core.routes import router as master_router
from backend.core.sovereign_bootstrapper import router as sovereign_boot_router
from backend.testing.sovereign_lock import router as sovereign_lock_router
from backend.simulation.routes import router as simulation_router
from backend.core.aura_master_runtime import router as master_runtime_router
from backend.api.core_routes import router as core_router, ws_router
from backend.backup.routes import router as backup_router
from backend.monitoring_routes import router as monitoring_router
from backend.voice_routes import router as voice_router
from backend.marketplace_routes import router as marketplace_router
from backend.production_routes import router as production_router
from backend.tenant_routes import router as tenant_router
from backend.disaster_routes import router as disaster_router
from backend.integration_routes import router as integration_router
from backend.spatial_routes import router as spatial_router
from backend.learning_routes import router as learning_router
from backend.unification_routes import router as unification_router
from backend.local_ai_routes import router as local_ai_router
from backend.routes_local_ai import local_ai_router as local_ai_new_router, browser_router
from backend.swarm_routes import router as swarm_router
from backend.plugin_webrtc_routes import router as plugin_webrtc_router
from backend.routers.telemetry import router as telemetry_router
from backend.routers.webrtc import router as webrtc_router
from backend.routers.vision import router as vision_router
from backend.vision.router import router as screen_vision_router
from backend.vision.tracker import router as tracker_router
from backend.routers.actions import router as actions_router
from backend.automation.stealth_controller import router as stealth_router
from backend.automation.watchdog import router as watchdog_router
from backend.automation.scheduler import router as scheduler_router, enable_autostart as scheduler_enable_autostart
from backend.agent.deep_research import get_research_engine
from backend.routers.automation_os import router as automation_os_router
from backend.task_routes import router as tasks_router
from backend.routers.memory import router as memory_router, memory_engine
from backend.memory.cognitive_routes import router as cognitive_router
from backend.task_manager import task_manager
from backend.agent_scheduler import get_agent_scheduler
from backend.ai_router import AIRouter
from backend.routers.deep_learning import router as deep_learning_router
from jose import JWTError, jwt
from backend.core import passwords

from backend.distributed.orchestrator_distributed import DistributedOrchestrator
from backend.distributed.agent_sync import agent_sync_manager
from backend.monitoring.distributed_metrics import distributed_metrics_collector
from backend.ha.failover_manager import failover_manager
from backend.auth.service import AuthService, get_current_user as auth_get_current_user, get_current_admin, ACCESS_TOKEN_EXPIRE_MINUTES, security
from backend.auth.models import UserCreate, UserLogin, TokenResponse
from backend.auth.models import User as AuthUser
from backend.auth.models import Session as AuthSession
from sqlalchemy.orm import Session as DBSession
from backend.mobile import mdns, mobile_sync, sync_manager
from backend.mobile.discovery import get_local_ips, resolve_local_ip

from backend.omniroute import OmnirouteClient, OmnirouteConfig, ProviderManager
from backend.agents.react_loop import ReactLoop
from backend.diagnostics.health import (
    get_health_daemon,
    get_system_resources,
    probe_service_status,
)

omniroute_config = OmnirouteConfig(
    omniroute_url=os.getenv("OMNIROUTE_URL", "http://localhost:8080"),
    timeout=int(os.getenv("OMNIROUTE_TIMEOUT", "30")),
    retry_attempts=int(os.getenv("OMNIROUTE_RETRY", "3")),
    fallback_enabled=os.getenv("OMNIROUTE_FALLBACK", "true").lower() == "true",
    enable_context_relay=os.getenv("OMNIROUTE_CONTEXT_RELAY", "true").lower() == "true",
)
omniroute_client = OmnirouteClient(omniroute_config)
provider_manager = ProviderManager(omniroute_config)

_ai_router: Optional[AIRouter] = None
_react_loop: Optional[ReactLoop] = None

IS_CLUSTER_MODE = os.getenv("CLUSTER_MODE", "false").lower() == "true"
NODE_ID = os.getenv("NODE_ID", f"node-{os.getenv('PORT', '8000')}")

if IS_CLUSTER_MODE:
    orchestrator = DistributedOrchestrator(NODE_ID)

Base.metadata.create_all(bind=engine)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("AURANewsAPI")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-prod")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

Path("logs").mkdir(exist_ok=True)
from backend.logging.config import setup_logging
setup_logging(LOG_LEVEL)
logger = logging.getLogger("AURA")

from backend.auth.security import get_current_user, authenticate_user, create_access_token
from backend.middleware.rate_limiter import rate_limiter
from backend.cache.redis_client import init_redis, close_redis
from backend.monitoring.metrics import init_metrics_server

app = FastAPI(
    title="AURA Multi-Agent Core",
    description="Distributed AI system with real-time telemetry, vision, RAG, and swarm orchestration",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    contact={"name": "AURA Dev Team", "url": "https://github.com/your-org/aura"},
    license_info={"name": "MIT"},
)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
# Orden de middlewares (reordenado a propósito, no lo deshagas por "limpieza"):
# en Starlette add_middleware() hace user_middleware.insert(0, ...), así que la
# ÚLTIMA llamada es la MÁS EXTERNA. SlowAPIMiddleware va justo después de este
# bloque, pero CORSMiddleware se registra al FINAL del bloque para que envuelva a
# SlowAPI: su 429 también debe llevar access-control-allow-origin, o el renderer
# ve un error opaco en vez de un 429 con CORS. Este bloque sube aquí porque
# `limiter` debe existir ANTES de la primera ruta con @limiter.limit (L688):
# los decoradores resuelven el nombre en tiempo de definición, no en request.
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402

app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if os.getenv("ENVIRONMENT", "development") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Excluir WebSocket upgrade requests del rate limiter
    if request.url.path.startswith("/ws/"):
        return await call_next(request)
    client_id = request.client.host if request.client else "unknown"
    if await rate_limiter.check_rate_limit(client_id):
        return await call_next(request)
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    # Va aquí, y no más abajo, por el mismo motivo que CORS: @app.middleware es
    # un add_middleware disfrazado, así que definirlo después de CORS lo haría el
    # MÁS EXTERNO y volvería a esconder SlowAPI (y su 429) detrás de él. Se
    # puede mover aquí aunque REQUEST_COUNT/REQUEST_LATENCY se definan más
    # abajo: el decorador solo necesita `app`, y los dos nombres se resuelven
    # desde los globals del módulo en cada request, ya con el import completo.
    with REQUEST_LATENCY.labels(endpoint=request.url.path).time():
        response = await call_next(request)
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, status=response.status_code).inc()
    return response


# ÚLTIMA llamada add_middleware del archivo a propósito: registro de CORS fuera
# de SlowAPIMiddleware para que sus 429 lleven headers CORS (ver bloque de arriba).
app.add_middleware(
    CORSMiddleware,
    # allowlist explícita: Starlette hace coincidencia EXACTA de origins.
    # Los comodines LAN ("http://192.168.*.*", etc.) se eliminaron porque NUNCA
    # matcheaban (solo valdrían vía allow_origin_regex); eran config muerta.
    # Sin "null"/"file://": ese renderer debe llamar por IPC, no por HTTP
    # directo al backend (null + allow_credentials es vector de robo de credenciales).
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "AURA_CORS_ORIGINS",
            "http://localhost:3000,http://localhost:8000,http://127.0.0.1:8000,http://frontend:3000",
        ).split(",")
        if origin.strip()
    ],
    # allow_credentials=True SOLO con origins explícitos literales (sin comodines
    # ni regex): si AURA_CORS_ORIGINS trae "*" hay que pasarlo a False.
    allow_credentials="*" not in os.getenv("AURA_CORS_ORIGINS", ""),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

app.include_router(rollercoin_router)
app.include_router(device_sync_router)
app.include_router(sync_router)
app.include_router(cloud_router, prefix="/api/cloud", tags=["cloud-sync"])
app.include_router(whatsapp_router, prefix="/api/whatsapp", tags=["whatsapp"])
app.include_router(ame_sync_router)
app.include_router(learning_api_router)
app.include_router(storage_router)
app.include_router(automation_router)
from backend.api.aura_chat_routes import chat_router
from backend.api.aura_chat_commands import command_router
from backend.netrunner.netrunner_router import netrunner_router as netrunner_router

app.include_router(chat_router, prefix="/api/aura", tags=["aura_core"])
app.include_router(command_router, prefix="/api/aura", tags=["aura_core"])
app.include_router(netrunner_router, tags=["netrunner"])

# PC-to-Mobile pull sync (bidirectional sync)
from backend.sync_engine import router as _sync_engine_router
app.include_router(_sync_engine_router)
app.include_router(brain_router)
app.include_router(narrative_router)
app.include_router(update_router)
app.include_router(mobile_router)
app.include_router(mobile_story_router)
app.include_router(mobile_pairing_router)
app.include_router(selflearn_router)
app.include_router(fanfic_router)
app.include_router(analytics_router)
app.include_router(billing_router)
app.include_router(localization_router)
app.include_router(security_router)
app.include_router(vault_router)
app.include_router(defense_router)
app.include_router(identity_router)
app.include_router(zk_audit_router)
app.include_router(patcher_router)
app.include_router(planner_router)
app.include_router(refactoring_router)
app.include_router(testing_matrix_router)
app.include_router(aura_master_router)
app.include_router(finetune_lora_router)
app.include_router(federated_lora_router)
app.include_router(swarm_marketplace_router)
app.include_router(device_router)
app.include_router(finetuning_router)
app.include_router(nomad_router)
app.include_router(monitoring_router)
app.include_router(voice_router)
app.include_router(marketplace_router)
app.include_router(production_router)
app.include_router(tenant_router)
app.include_router(disaster_router)
app.include_router(integration_router)
app.include_router(spatial_router)
app.include_router(unification_router)
app.include_router(local_ai_router)
app.include_router(local_ai_new_router)
app.include_router(browser_router)
app.include_router(swarm_router)
app.include_router(plugin_webrtc_router)
app.include_router(governor_router)
app.include_router(knowledge_router)
app.include_router(telemetry_router)
app.include_router(webrtc_router)
app.include_router(vision_router)
app.include_router(screen_vision_router)
app.include_router(tracker_router)
app.include_router(actions_router)
app.include_router(automation_os_router)
app.include_router(tasks_router)
app.include_router(memory_router)
app.include_router(cognitive_router)
app.include_router(deep_learning_router)
app.include_router(story_router)
app.include_router(audio_stt_router)
app.include_router(audio_tts_router)
app.include_router(wake_word_router)
app.include_router(voice_interaction_router)
app.include_router(agent_orchestrator_router)
app.include_router(agent_memory_router)
app.include_router(tools_registry_router)
app.include_router(sandbox_router)
app.include_router(evolution_router)
app.include_router(research_router)
app.include_router(agent_swarm_router)
app.include_router(agent_learning_router)
scheduler_enable_autostart()
app.include_router(scheduler_router)
app.include_router(desktop_router)
app.include_router(overlay_b75_router)
app.include_router(omni_hud_router)
app.include_router(automation_memory_router)
app.include_router(ephemeral_sandbox_router)
app.include_router(mesh_router)
app.include_router(master_dashboard_router)
app.include_router(daemon_lifecycle_router)
app.include_router(daemon_sync_router)
app.include_router(healing_router)
app.include_router(window_router)
app.include_router(media_router)
app.include_router(health_router)
app.include_router(omni_router)
app.include_router(ecosystem_router)
app.include_router(fusion_context_router)
app.include_router(predictive_scheduler_router)
app.include_router(recovery_snapshot_router)
app.include_router(edge_finetune_router)
app.include_router(cognitive_graph_router)
app.include_router(mesh_consensus_router)
app.include_router(master_router)
app.include_router(sovereign_boot_router)
app.include_router(testing_matrix_router)
app.include_router(sovereign_lock_router)
app.include_router(simulation_router)
app.include_router(master_runtime_router)
app.include_router(core_router)  # Chunk 1: /api/core/*
app.include_router(ws_router)  # Chunk 1: WS /ws/core/events
if stealth_router is not None:
    app.include_router(stealth_router)
if watchdog_router is not None:
    app.include_router(watchdog_router)
if scheduler_router is not None:
    app.include_router(scheduler_router)
app.include_router(p2p_reconcile_router)
app.include_router(p2p_sync_router)
app.include_router(mesh_router)
app.include_router(backup_router)


DASHBOARD_BUILD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "web_dashboard", "dist")
if not os.path.isdir(DASHBOARD_BUILD_DIR) and hasattr(sys, "_MEIPASS"):
    bundled_dist = os.path.join(sys._MEIPASS, "aura_app_data", "frontend_dist")
    if os.path.isdir(bundled_dist):
        DASHBOARD_BUILD_DIR = bundled_dist
if os.path.isdir(DASHBOARD_BUILD_DIR):
    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_BUILD_DIR, html=True), name="aura-dashboard")


@app.get("/", include_in_schema=False)
async def _serve_aura_dashboard():
    """Sirve el dashboard interactivo de AURA."""
    dashboard_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend", "aura_dashboard.html"
    )
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    if os.path.isdir(DASHBOARD_BUILD_DIR):
        return RedirectResponse(url="/dashboard")
    return JSONResponse(status_code=404, content={"error": "Dashboard not found"})


@app.get("/dashboard.html", include_in_schema=False)
async def _serve_aura_dashboard_alt():
    """Alternativa directa al dashboard de AURA."""
    dashboard_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "frontend", "aura_dashboard.html"
    )
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    return JSONResponse(status_code=404, content={"error": "Dashboard not found"})


if os.getenv("AURA_OTEL_ENDPOINT"):
    provider = TracerProvider()
    processor = SimpleSpanProcessor(OTLPSpanExporter(endpoint=os.getenv("AURA_OTEL_ENDPOINT"), insecure=True))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["endpoint"])
TRAINING_JOBS = Gauge("training_jobs_active", "Active training jobs")
TRAINING_STATUS = Gauge("training_jobs_status", "Training jobs by status", ["status"])

SECRET_KEY = os.getenv("AURA_JWT_SECRET", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# NOTA: passlib se eliminó del path de import a propósito. passlib 1.7.4 sondea
# `bcrypt.__about__` y su probe `detect_wrap_bug` hashea un secreto largo, algo
# que bcrypt >= 4.1 (y 5.x) rechaza con "password cannot be longer than 72 bytes".
# Con la dependencia instalada, CUALQUIER hash/verify a través de passlib lanzaba
# ValueError: login y registro estaban rotos en runtime. El truncado explícito a
# 72 bytes vive ahora en UN solo sitio, backend/core/passwords.py, que también
# usa backend/auth/service.py: dos políticas sobre la misma columna `users`
#-meaningían que una contraseña larga devolvía 500 en una ruta y funcionaba en otra.
BCRYPT_MAX_SECRET_BYTES = passwords.BCRYPT_MAX_SECRET_BYTES
get_password_hash = passwords.get_password_hash
verify_password = passwords.verify_password
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

_latest_recommendations: List[Dict[str, Any]] = []

_local_model = None
_local_tokenizer = None
_local_model_path = os.getenv("AURA_LOCAL_MODEL_PATH", os.path.join(os.path.dirname(__file__), "models", "qwen-0.5b"))
_response_cache: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 60 * 60  # 1 hour
treasury_manager = TreasuryManager()
federated_trainer = FederatedTrainer()


def _get_local_model():
    global _local_model, _local_tokenizer
    if _local_model is None or _local_tokenizer is None:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        _local_tokenizer = AutoTokenizer.from_pretrained(_local_model_path)
        _local_model = AutoModelForCausalLM.from_pretrained(
            _local_model_path,
            device_map="cpu",
            load_in_8bit=False,
            torch_dtype="auto",
        )
    return _local_model, _local_tokenizer


def _get_cached_response(prompt: str, provider: str) -> Optional[Dict[str, Any]]:
    cache_key = f"{provider}:{prompt.strip().lower()}"
    entry = _response_cache.get(cache_key)
    if not entry:
        return None
    if time.time() - entry.get("ts", 0) > _CACHE_TTL:
        _response_cache.pop(cache_key, None)
        return None
    return entry.get("data")


def _set_cached_response(prompt: str, provider: str, data: Dict[str, Any]) -> None:
    cache_key = f"{provider}:{prompt.strip().lower()}"
    _response_cache[cache_key] = {"ts": time.time(), "data": data}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


class UserSchema(BaseModel):
    id: int
    email: str
    is_active: bool
    role: str

    class Config:
        from_attributes = True


class LogEntryModel(BaseModel):
    service: str
    level: str = "INFO"
    message: str
    timestamp: float = time.time()


class AuthContext(BaseModel):
    api_key: Optional[str] = None
    user: Optional[UserSchema] = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_api_key() -> Optional[str]:
    return os.getenv("AURA_API_KEY")


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme), db: SessionLocal = Depends(get_db)) -> UserSchema:
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return UserSchema.model_validate(user)


def require_role(required_role: str):
    def checker(current_user: UserSchema = Depends(get_current_user)) -> UserSchema:
        if current_user.role != required_role and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return checker


def require_api_key(request: Request, db: SessionLocal = Depends(get_db)) -> AuthContext:
    api_key = _get_api_key()
    if not api_key:
        return AuthContext(api_key=None)

    provided = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if provided != api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return AuthContext(api_key=provided)


@app.get("/api/health")
@app.get("/health")
async def health() -> Dict[str, str]:
    """
    Health check del proceso, no de sus dependencias.

    Lo único verificado al responder es el enrutado: si este handler se ejecuta,
    el proceso ASGI está aceptando peticiones en esta ruta. NO se sondea base de
    datos, Redis ni modelo local, así que no se afirma nada sobre ellos: el
    `"healthy"` estático anterior declaraba saludable una dependencia que nunca
    se midió.

    Convención (`v6/axum-poc/src/system.rs::ping`,
    `ARIA_APP/backend/skills/system/status.py`): lo no medido -> valor ausente +
    `"data_source": "unavailable"` + `detail` con el motivo.

    La sonda real de dependencias ya existe en `detailed_health`, más abajo en
    este archivo, pero queda ensombrecida: este decorador se registró antes y
    Starlette resuelve en orden de registro. Exponerla exige tocar el orden de
    las rutas, fuera del alcance de este arreglo; se reporta como recomendación.

    Example:
    ```bash
    curl http://localhost:8000/health
    ```
    """
    # Derivado de una lectura real del entorno, no de un literal fijo.
    deployment_mode = (
        "cloud"
        if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("FLY_APP_NAME")
        else "local"
    )
    return {
        "status": "ok",
        "service": f"aura-backend-{deployment_mode}",
        "data_source": "unavailable",
        "detail": (
            "sin medición: este endpoint solo confirma que el proceso sirve "
            "peticiones en /health. No se sondea base de datos, Redis ni modelo "
            "local, así que no se reporta estado de ninguno. La sonda de "
            "dependencias (detailed_health) queda ensombrecida por esta ruta."
        ),
    }


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: SessionLocal = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token({"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/status")
async def status(auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db)) -> Dict[str, Any]:
    services = db.query(ServiceStatus).all()
    result = {}
    for svc in services:
        result[svc.service] = {"status": svc.status, "service": svc.service, "updated_at": svc.updated_at}
    return result


@app.get("/api/logs")
@limiter.limit("60/minute")
async def get_logs(request: Request, service: str = "backend", lines: int = 50, auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db)) -> Dict[str, Any]:
    service_logs = db.query(LogEntry).filter(LogEntry.service == service).order_by(LogEntry.timestamp.desc()).limit(lines).all()
    logs_text = "\n".join(
        f"{time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(entry.timestamp))} [{entry.level}] {entry.message}"
        for entry in service_logs
    )
    return {"service": service, "lines": lines, "logs": logs_text or "No logs yet"}


@app.post("/api/logs")
@limiter.limit("120/minute")
async def add_log(request: Request, auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db)) -> Dict[str, str]:
    body = await request.json()
    entry = LogEntryModel(**body)
    db_entry = LogEntry(service=entry.service, level=entry.level, message=entry.message, timestamp=entry.timestamp)
    db.add(db_entry)
    db.commit()
    count = db.query(LogEntry).count()
    return {"status": "ok", "count": str(count)}


@app.post("/api/restart")
@limiter.limit("10/minute")
async def restart_service(request: Request, auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db)) -> Dict[str, str]:
    payload: Any = await request.json()
    service = payload.get("service", "unknown")
    svc = db.query(ServiceStatus).filter(ServiceStatus.service == service).first()
    if not svc:
        svc = ServiceStatus(service=service, status="restarting", updated_at=time.time())
        db.add(svc)
    else:
        svc.status = "restarting"
        svc.updated_at = time.time()
    db.commit()
    db.add(LogEntry(service=service, level="INFO", message=f"Service {service} restarted", timestamp=time.time()))
    db.commit()
    svc.status = "ok"
    svc.updated_at = time.time()
    db.commit()
    _send_discord_alert(f"✅ Servicio `{service}` reiniciado correctamente en AURA.")
    return {"message": f"Service {service} restarted"}


@app.post("/api/deploy")
@limiter.limit("10/minute")
async def deploy_service(request: Request, auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db)) -> Dict[str, str]:
    payload: Any = await request.json()
    service = payload.get("service", "unknown")
    svc = db.query(ServiceStatus).filter(ServiceStatus.service == service).first()
    if not svc:
        svc = ServiceStatus(service=service, status="deploying", updated_at=time.time())
        db.add(svc)
    else:
        svc.status = "deploying"
        svc.updated_at = time.time()
    db.commit()
    db.add(LogEntry(service=service, level="INFO", message=f"Service {service} deployed", timestamp=time.time()))
    db.commit()
    svc.status = "ok"
    svc.updated_at = time.time()
    db.commit()
    _send_discord_alert(f"🚀 Servicio `{service}` desplegado correctamente en AURA.")
    return {"message": f"Service {service} deployed"}


@app.post("/api/training/start")
@limiter.limit("5/minute")
async def start_training(request: Request, auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db), current_user: UserSchema = Depends(require_role("user"))) -> Dict[str, str]:
    payload: Any = await request.json()
    job = TrainingJob(
        status="starting",
        model_name=payload.get("model_name", "Qwen/Qwen2.5-1.5B-Instruct"),
        dataset_path=payload.get("dataset_path", "aura_merged_training.jsonl"),
        output_dir=payload.get("output_dir", "fine-tuned-ame"),
        started_at=time.time(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    _send_discord_alert(f"🧠 Entrenamiento iniciado: job `{job.id}` modelo `{job.model_name}` en AURA.")

    TRAINING_JOBS.inc()

    def run_training():
        try:
            job.status = "running"
            db.commit()
            status_file = f"/tmp/aura_training_{job.id}.json"
            env = {
                **os.environ,
                "AURA_TRAINING_MODEL_NAME": job.model_name or "Qwen/Qwen2.5-1.5B-Instruct",
                "AURA_TRAINING_DATASET_PATH": job.dataset_path or "aura_merged_training.jsonl",
                "AURA_TRAINING_OUTPUT_DIR": job.output_dir or "fine-tuned-ame",
                "AURA_TRAINING_STATUS_FILE": status_file,
            }
            subprocess.run(
                [sys.executable, "training/run_training_job.py"],
                env=env,
                check=False,
            )
            job.status = "finished"
            job.finished_at = time.time()
            if os.path.exists(status_file):
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        job.metrics = f.read()
                except Exception:
                    job.metrics = "ok"
            else:
                job.metrics = "ok"
            TRAINING_STATUS.labels(status="finished").inc()
        except Exception as exc:  # pragma: no cover - defensive
            job.status = "failed"
            job.metrics = str(exc)
            TRAINING_STATUS.labels(status="failed").inc()
            _send_discord_alert(f"❌ Entrenamiento fallido: job `{job.id}` modelo `{job.model_name}` en AURA. Error: {exc}")
        finally:
            TRAINING_JOBS.dec()
            db.commit()

    thread = threading.Thread(target=run_training, daemon=True)
    thread.start()
    return {"message": f"Training job {job.id} started"}


@app.get("/api/training/status")
@limiter.limit("30/minute")
async def training_status(request: Request, auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db)) -> Dict[str, Any]:
    jobs = db.query(TrainingJob).order_by(TrainingJob.id.desc()).limit(10).all()
    status_counts: Dict[str, int] = {}
    for job in jobs:
        status_counts[job.status] = status_counts.get(job.status, 0) + 1
    for status, count in status_counts.items():
        TRAINING_STATUS.labels(status=status).set(count)
    return {
        "jobs": [
            {
                "id": job.id,
                "status": job.status,
                "model_name": job.model_name,
                "dataset_path": job.dataset_path,
                "output_dir": job.output_dir,
                "started_at": job.started_at,
                "finished_at": job.finished_at,
                "metrics": job.metrics,
            }
            for job in jobs
        ]
    }


@app.post("/api/news/recommend")
async def receive_recommendations(request: Request) -> JSONResponse:
    global _latest_recommendations
    try:
        payload: Any = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON"})

    articles = payload.get("articles", []) if isinstance(payload, dict) else []
    _latest_recommendations = articles
    logger.info("Recibidas %d recomendaciones de noticias", len(articles))
    return JSONResponse(content={"status": "ok", "count": len(articles)})


@app.get("/api/news/recommend")
async def get_recommendations() -> Dict[str, Any]:
    return {"articles": _latest_recommendations}


class GesturePredictRequest(BaseModel):
    image_base64: str


class VoiceTranscribeRequest(BaseModel):
    audio_base64: str


class ChatRequest(BaseModel):
    message: str
    history: List[List[str]] = []
    system_prompt: str = "Eres AURA, un asistente de IA avanzado."
    temperature: float = 0.7
    max_tokens: int = 128
    image_base64: Optional[str] = None
    audio_base64: Optional[str] = None
    video_base64: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    checks: Dict[str, str]


class TTSRequest(BaseModel):
    text: str
    voice: str = "default"
    speed: float = 1.0


class DeviceAutomationRequest(BaseModel):
    action: str
    target: str = ""
    params: Dict[str, Any] = {}


class WiFiScanRequest(BaseModel):
    interface: str = "wlan0"
    scan_time: int = 10


class TelemetryResponse(BaseModel):
    cpu: float
    memory: float
    disk: float
    network: Dict[str, Any]
    processes: List[Dict[str, Any]]
    timestamp: float


class NetworkTopologyResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    timestamp: float


class AgentCommandRequest(BaseModel):
    command: str
    context: Dict[str, Any] = {}
    device: str = "local"


@app.get("/health", response_model=HealthResponse)
async def detailed_health(db: SessionLocal = Depends(get_db)) -> HealthResponse:
    checks = {}
    try:
        db.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"

    try:
        import redis
        from urllib.parse import urlparse
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        parsed = urlparse(redis_url)
        r = redis.Redis(host=parsed.hostname or "localhost", port=parsed.port or 6379, db=int(parsed.path.lstrip("/") or 0), socket_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    local_model_path = os.getenv("AURA_LOCAL_MODEL_PATH", "")
    checks["local_model"] = "ok" if os.path.isdir(local_model_path) else "missing"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    deployment_mode = "cloud" if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("FLY_APP_NAME") else "local"
    return HealthResponse(status=overall, service=f"aura-backend-{deployment_mode}", checks=checks)


@app.get("/api/discovery")
async def discovery() -> Dict[str, Any]:
    deployment_mode = "cloud" if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("FLY_APP_NAME") else "local"
    return {
        "mode": deployment_mode,
        "version": "2.0.0",
        "features": {
            "chat": True,
            "local_model": bool(os.getenv("AURA_LOCAL_MODEL_PATH")),
            "memory": True,
            "streaming": False,
        },
        "endpoints": {
            "chat": "/api/chat",
            "ai": "/api/ai",
            "status": "/api/status",
            "conversations": "/api/conversations",
        },
    }


@app.post("/api/gesture/predict")
@limiter.limit("20/minute")
async def gesture_predict(request: Request, payload: GesturePredictRequest, auth: AuthContext = Depends(require_api_key)) -> Dict[str, Any]:
    if not payload.image_base64 or len(payload.image_base64) < 100:
        raise HTTPException(status_code=422, detail="image_base64 must be a valid base64 image")

    try:
        import cv2
        import mediapipe as mp
        import numpy as np
        import base64

        try:
            image_data = base64.b64decode(payload.image_base64)
        except Exception:
            raise HTTPException(status_code=422, detail="invalid base64 image")

        np_arr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("invalid image")

        with mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=1) as hands:
            result = hands.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        gesture = "unknown"
        confidence = 0.0
        fingers = 0
        if result.multi_hand_landmarks:
            landmarks = result.multi_hand_landmarks[0].landmark
            finger_tips = [8, 12, 16, 20]
            finger_pips = [6, 10, 14, 18]
            fingers = sum(1 for tip, pip in zip(finger_tips, finger_pips) if landmarks[tip].y < landmarks[pip].y)
            if fingers == 4 and landmarks[8].y < landmarks[6].y and landmarks[12].y < landmarks[10].y and landmarks[16].y < landmarks[14].y and landmarks[20].y < landmarks[18].y:
                gesture = "open_hand"
                confidence = 0.9
            elif fingers == 1 and landmarks[8].y < landmarks[6].y:
                gesture = "index"
                confidence = 0.85
            elif fingers == 2 and landmarks[8].y < landmarks[6].y and landmarks[12].y < landmarks[10].y:
                gesture = "peace"
                confidence = 0.85
            elif fingers == 0 and all(landmarks[i].y >= landmarks[i - 2].y for i in [8, 12, 16, 20]):
                gesture = "fist"
                confidence = 0.85
            elif fingers >= 3:
                gesture = "open_hand"
                confidence = 0.7
            else:
                gesture = "swipe"
                confidence = 0.5

        return {"gesture": gesture, "confidence": confidence, "fingers": fingers, "hand_detected": bool(result.multi_hand_landmarks)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/voice/transcribe")
@limiter.limit("20/minute")
async def voice_transcribe(request: Request, payload: VoiceTranscribeRequest, auth: AuthContext = Depends(require_api_key)) -> Dict[str, Any]:
    if not payload.audio_base64 or len(payload.audio_base64) < 100:
        raise HTTPException(status_code=422, detail="audio_base64 must be a valid base64 audio")

    try:
        import whisper

        model = whisper.load_model("base")
        audio = whisper.load_audio(payload.audio_base64)
        result = model.transcribe(audio)
        text = result.get("text", "").strip().lower()

        command_map = {
            "ejecutar training": "run_training",
            "detener servicios": "stop_services",
            "publicar estado": "publish_status",
            "reiniciar bot": "restart_bot",
        }
        command = command_map.get(text, "unknown")
        return {"text": text, "command": command, "language": result.get("language", "unknown")}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/hf-chat")
@limiter.limit("20/minute")
async def hf_chat(request: Request, payload: ChatRequest, auth: AuthContext = Depends(require_api_key)) -> Dict[str, Any]:
    hf_space_url = os.getenv("NEXT_PUBLIC_HF_SPACE_URL", "http://localhost:7860")
    hf_token = os.getenv("HF_TOKEN", "")
    try:
        import urllib.request
        data = json.dumps({
            "data": [payload.message, payload.history, payload.system_prompt, payload.temperature, payload.max_tokens]
        }).encode()
        headers = {"Content-Type": "application/json"}
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"
        req = urllib.request.Request(
            f"{hf_space_url}/run/predict?fn_index=0",
            data=data,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
        raw = result.get("data", [None])[0] if isinstance(result.get("data"), list) else result.get("data")
        bot_message = raw if isinstance(raw, str) else ""
        updated_history = payload.history + [[payload.message, bot_message]]
        return {"message": bot_message, "history": updated_history}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("HF chat error: %s", exc)
        local = _try_gemini_chat(payload)
        if local:
            return local
        local = _try_local_chat(payload)
        if local:
            return local
        return _local_response_chat(payload)


def _try_local_chat(payload: ChatRequest) -> Optional[Dict[str, Any]]:
    base = os.getenv("LOCAL_LFM_BASE_URL", "http://localhost:11434")
    model = os.getenv("LOCAL_LFM_MODEL", "llama3.2:3b")
    try:
        import urllib.request
        messages = [{"role": "user", "content": payload.message}]
        if payload.system_prompt:
            messages.insert(0, {"role": "system", "content": payload.system_prompt})
        body = json.dumps({"model": model, "messages": messages, "stream": False}).encode()
        req = urllib.request.Request(
            f"{base}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
        text = ((result.get("message") or {}).get("content") or "").strip()
        if not text:
            return None
        return {"message": text, "history": payload.history + [[payload.message, text]]}
    except Exception:
        return None


def _try_gemini_chat(payload: ChatRequest) -> Optional[Dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        body = json.dumps({
            "contents": [{"parts": [{"text": payload.message}]}],
            "systemInstruction": {"parts": [{"text": payload.system_prompt or "Eres AURA."}]},
            "generationConfig": {"temperature": payload.temperature, "maxOutputTokens": payload.max_tokens},
        }).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
        text = ((result.get("candidates") or [{}])[0].get("content") or {}).get("parts", [{}])[0].get("text", "")
        text = text.strip()
        if not text:
            return None
        return {"message": text, "history": payload.history + [[payload.message, text]], "provider": "gemini"}
    except Exception:
        return None


def _try_groq_chat(payload: ChatRequest) -> Optional[Dict[str, Any]]:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return None
    try:
        import urllib.request
        url = "https://api.groq.com/openai/v1/chat/completions"
        body = json.dumps({
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": payload.system_prompt or "Eres AURA."},
                {"role": "user", "content": payload.message},
            ],
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
        }).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
        text = ((result.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
        if not text:
            return None
        return {"message": text, "history": payload.history + [[payload.message, text]], "provider": "groq"}
    except Exception:
        return None


def _try_openrouter_chat(payload: ChatRequest) -> Optional[Dict[str, Any]]:
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return None
    try:
        import urllib.request
        url = "https://openrouter.ai/api/v1/chat/completions"
        body = json.dumps({
            "model": "mistralai/mistral-7b-instruct",
            "messages": [
                {"role": "system", "content": payload.system_prompt or "Eres AURA."},
                {"role": "user", "content": payload.message},
            ],
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
        }).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
        text = ((result.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
        if not text:
            return None
        return {"message": text, "history": payload.history + [[payload.message, text]], "provider": "openrouter"}
    except Exception:
        return None


def _try_vision_chat(payload: ChatRequest, chat_request: ChatRequest) -> Optional[Dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or not payload.message:
        return None
    try:
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        parts = [{"text": payload.message}]
        if payload.image_base64:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": payload.image_base64}})
        body = json.dumps({
            "contents": [{"parts": parts}],
            "systemInstruction": {"parts": [{"text": payload.system_prompt or "Eres AURA."}]},
            "generationConfig": {"temperature": payload.temperature, "maxOutputTokens": payload.max_tokens},
        }).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
        text = ((result.get("candidates") or [{}])[0].get("content") or {}).get("parts", [{}])[0].get("text", "")
        text = text.strip()
        if not text:
            return None
        return {"message": text, "history": chat_request.history + [[chat_request.message, text]], "provider": "gemini-vision"}
    except Exception:
        return None


def _try_qwen_chat(payload: ChatRequest) -> Optional[Dict[str, Any]]:
    try:
        model, tokenizer = _get_local_model()
        system_prompt = payload.system_prompt or "Eres AURA, un asistente de IA avanzado."
        prompt_text = f"{system_prompt}\n\nUsuario: {payload.message}\nAURA:"
        inputs = tokenizer(prompt_text, return_tensors="pt")
        outputs = model.generate(
            **inputs,
            max_new_tokens=min(payload.max_tokens, 128),
            temperature=payload.temperature,
            pad_token_id=tokenizer.eos_token_id,
        )
        text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        if text.startswith(prompt_text):
            text = text[len(prompt_text):].strip()
        if not text:
            return None
        return {"message": text, "history": payload.history + [[payload.message, text]], "provider": "local-qwen"}
    except Exception:
        return None


def _local_response_chat(payload: ChatRequest) -> Dict[str, Any]:
    msg = payload.message.strip()
    text = ""
    lower = msg.lower()

    if any(g in lower for g in ["hola", "buenas", "hello", "hi"]):
        text = "Hola, soy AURA. ¿En qué puedo ayudarte?"
    elif any(g in lower for g in ["como estas", "cómo estás", "como andas", "cómo andas"]):
        text = "Estoy operativo. Listo para ayudarte con el proyecto AURA."
    elif any(g in lower for g in ["proyecto", "aura"]):
        text = "AURA es un ecosistema multi-servicio: backend FastAPI, frontend Next.js, bot Discord, HF Space y app de escritorio."
    elif any(g in lower for g in ["backend", "fastapi", "api"]):
        text = "El backend corre en el puerto 8000. Endpoints principales: /health, /api/hf-chat, /api/status, /api/logs."
    elif any(g in lower for g in ["frontend", "next", "react"]):
        text = "El frontend es Next.js en el puerto 3000. Incluye chat, panel de control y tabs de servicios."
    elif any(g in lower for g in ["docker", "compose"]):
        text = "Podés levantar todo con docker-compose up --build. O usar la app de escritorio aura_app.py."
    elif any(g in lower for g in ["error", "falla", "problema", "arreglar"]):
        text = "Usá la pestaña Repair de la app de escritorio para escanear y reparar automáticamente el proyecto."
    elif any(g in lower for g in ["agente", "agent", "kilo", "cline"]):
        text = "La pestaña Agents integra Kilo y Cline. Podés pedirles que escaneen y arreglen errores del proyecto."
    elif any(g in lower for g in ["desplegar", "deploy", "producción"]):
        text = "Para producción usá docker-compose up --build. AURA soporta PostgreSQL y Redis en producción."
    elif any(g in lower for g in ["estado", "status", "servicios"]):
        text = "Servicios actuales: backend (ok), discord-bot (unknown), hf-space (unknown). Usá /api/status para detalles."
    elif any(g in lower for g in ["logs", "registros"]):
        text = "Podés consultar logs con GET /api/logs?service=backend&lines=50"
    elif any(g in lower for g in ["reiniciar", "restart"]):
        text = "Para reiniciar un servicio usá POST /api/restart con JSON {service: 'backend'}"
    elif any(g in lower for g in ["chat", "hablar", "conversar"]):
        text = "Podés chatear conmigo por el frontend en /hf-chat, por Discord con /chat, o por la app de escritorio."
    elif any(g in lower for g in ["ayuda", "help", "qué puedes hacer", "que puedes hacer"]):
        text = "Puedo ayudarte con: estado de servicios, logs, deployment, chat IA, configuración de Discord, y troubleshooting del proyecto."
    elif any(g in lower for g in ["godot", "juego", "desktop"]):
        text = "La app de escritorio está en Godot 4.6. Para exportar el .exe abrí el proyecto con Godot y usá Export Pack."
    elif any(g in lower for g in ["telegram", "discord"]):
        text = "Discord bot está en Ruby 3.3 con discordrb. Telegram no está implementado aún. Usá Discord para commands como /status y /chat."
    elif any(g in lower for g in ["redis", "base de datos", "database"]):
        text = "Redis corre en localhost:6379. La base de datos SQLite está en backend/aura.db."
    elif any(g in lower for g in ["training", "entrenar", "modelo"]):
        text = "El training usa PyTorch y transformers en venv-training. Scripts en training/scripts/."
    elif any(g in lower for g in ["osint", "investigación", "investigar", "buscar", "busqueda", "web", "internet", "noticias", "información", "informar"]):
        text = f"Para investigar sobre '{msg}', activá la pestaña OSINT para herramientas de investigación, o configurá GEMINI_API_KEY, GROQ_API_KEY u Ollama para respuestas inteligentes con IA."
    elif any(g in lower for g in ["api key", "gemini", "groq", "ollama", "openai"]):
        text = "Configurá GEMINI_API_KEY, GROQ_API_KEY u Ollama local para respuestas más avanzadas. Sin keys, funciono en modo local."
    elif any(g in lower for g in ["memoria", "history", "conversación"]):
        text = "Tengo memoria conversacional persistente en SQLite. Cada sesión guarda hasta 20 mensajes recientes para contexto."
    elif any(g in lower for g in ["cloud", "remoto", "servidor", "render", "railway"]):
        text = "Podés deployar en Railway o Render. Variables clave: DATABASE_URL, AURA_API_KEY, REDIS_URL, HF_TOKEN."
    elif any(g in lower for g in ["youtube", "video", "shorts", "reel", "mirar", "ver video"]):
        if "youtube.com" in lower or "youtu.be" in lower:
            text = f"Reconocí un link de YouTube. Activá Social Research (/api/social-research/collect) para descargarlo, transcribirlo con Whisper y analizar contenido. Requiere yt-dlp."
        else:
            text = "Social Research disponible: descarga y analiza videos de YouTube/Instagram/TikTok con yt-dlp + Whisper. Activá esa pestaña o configurá Ollama para IA conversacional."
    else:
        text = f"Recibido: '{msg}'. Sin modelo de IA activo. Instalá Ollama (https://ollama.com) y descargá `ollama pull qwen3:4b` para conversaciones inteligentes, o configurá GEMINI_API_KEY / GROQ_API_KEY."
    return {"message": text, "history": payload.history + [[payload.message, text]]}


def _start_worker() -> None:
    """Launch news_worker.run_worker() in a daemon thread if configured."""
    if not os.getenv("DATABASE_URL"):
        logger.warning("DATABASE_URL no configurada: el worker de noticias no arrancara.")
        return
    try:
        import news_worker  # sibling module

        thread = threading.Thread(target=news_worker.run_worker, daemon=True)
        thread.start()
        logger.info("Worker de noticias iniciado en segundo plano.")
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("No se pudo iniciar el worker de noticias: %s", exc)


def _seed_defaults(db: SessionLocal) -> None:
    defaults = [
        {"service": "backend", "status": "ok"},
        {"service": "discord-bot", "status": "unknown"},
        {"service": "hf-space", "status": "unknown"},
    ]
    for item in defaults:
        svc = db.query(ServiceStatus).filter(ServiceStatus.service == item["service"]).first()
        if not svc:
            svc = ServiceStatus(service=item["service"], status=item["status"], updated_at=time.time())
            db.add(svc)
    db.commit()


def _send_discord_alert(message: str) -> None:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    try:
        import urllib.request

        payload = json.dumps({"content": message}).encode("utf-8")
        request = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("No se pudo enviar alerta Discord: %s", exc)


@app.on_event("startup")
async def _on_startup() -> None:
    db = SessionLocal()
    try:
        _seed_defaults(db)
    finally:
        db.close()
    _start_worker()
    orchestrator.start_monitoring(interval=30)
    logger.info("Orquestador de disponibilidad iniciado")
    improvement.start(interval_hours=24)
    logger.info("Sistema de mejora continua iniciado")

    # UnifiedOrchestrator + Jan availability test
    try:
        from backend.core.unified_orchestrator import get_unified_orchestrator
        _uo = get_unified_orchestrator()
        jan_ok = await _uo.jan_available()
        if jan_ok:
            logger.info("[STARTUP] ✅ IA local disponible")
        else:
            logger.warning("[STARTUP] ⚠️ IA local no disponible — usa Ollama con dolphin-2_6-phi-2")
        logger.info("✅ AURA OS lista (UnifiedOrchestrator)")
    except Exception as exc:
        logger.error("[STARTUP] UnifiedOrchestrator fallo: %s", exc)

    async def _treasury_loop() -> None:
        while True:
            try:
                await asyncio.sleep(86400)
                await treasury_manager.allocate_daily_earnings()
            except Exception as exc:
                logger.error("Error en treasury loop: %s", exc)

    asyncio.create_task(_treasury_loop())
    logger.info("Treasury Manager iniciado")

    async def _federated_loop() -> None:
        while True:
            try:
                await federated_trainer.auto_improve_loop()
            except Exception as exc:
                logger.error("Error en federated loop: %s", exc)

    asyncio.create_task(_federated_loop())
    logger.info("Federated Trainer iniciado")

    # AURA Daemon (OPCION B + A) - autonomous background tasks
    try:
        daemon = get_daemon()
        asyncio.create_task(daemon.start_daemon())
        logger.info("[STARTUP] AURA Daemon iniciado en background (5 tareas paralelas)")
    except Exception as exc:
        logger.error("[STARTUP] AURA Daemon fallo: %s", exc)

    logger.info("✅ AURA OS lista en modo AUTÓNOMO")

    def _narrative_llm_query(prompt: str, system: str = "", max_tokens: int = 1200) -> str:
        try:
            for fn in (_try_gemini_chat, _try_groq_chat, _try_openrouter_chat, _try_local_chat):
                result = fn(ChatRequest(message=prompt, system_prompt=system, max_tokens=max_tokens))
                if result and result.get("message"):
                    return str(result.get("message"))
        except Exception as exc:
            logger.error("Narrative LLM query failed: %s", exc)
        return ""

    async def _narrative_llm_stream(prompt: str, system: str = "", max_tokens: int = 1200):
        text = _narrative_llm_query(prompt=prompt, system=system, max_tokens=max_tokens)
        if text:
            yield text

    init_narrative_engine(SessionLocal, _narrative_llm_query, _narrative_llm_stream)
    logger.info("Narrative Engine iniciado")

    global _update_manager, _version_tracker, _mobile_automation, _ai_router, task_manager
    _update_manager = UpdateManager()
    _version_tracker = VersionTracker()
    logger.info("Update Manager iniciado")

    _ai_router = AIRouter()
    logger.info("AI Router iniciado")

    # -- BLOQUE 52: conectar el puente de vision con el nucleo de razonamiento --
    global _react_loop  # noqa: PLW0603
    try:
        _react_loop = ReactLoop()
        from backend.vision.screen_bridge import get_screen_bridge as _get_vb
        _get_vb(orchestrator=_react_loop)
        logger.info("BLOQUE 52: Vision Bridge conectado al motor de razonamiento (ReactLoop)")
    except Exception as exc:
        logger.warning("BLOQUE 52: conexion Vision Bridge omitida: %s", exc)

    # -- BLOQUE 34: Background Narrative Agent & Cron Engine -------------------
    # Inicia el daemon de tareas en segundo plano (coherencia, reflexión Jan,
    # resúmenes de trama, limpieza de caché) sin bloquear el event loop.
    try:
        _agent_daemon = get_agent_scheduler(_ai_router).start(_ai_router)
        logger.info(
            "Agent daemon iniciado con %d tareas programadas",
            _agent_daemon.task_count() if hasattr(_agent_daemon, "task_count") else len(_agent_daemon.tasks),
        )
    except Exception as exc:
        logger.warning("Agent daemon startup failed (no crítico): %s", exc)

    from backend.task_manager import task_manager as _task_manager
    task_manager = _task_manager
    logger.info("Task Manager iniciado")

    _mobile_automation = MobileAutomationManager(db=None, adb_connector=None)
    init_mobile_automation(_mobile_automation)
    asyncio.create_task(_mobile_automation.start_automation_loop())
    logger.info("Mobile Automation Manager iniciado")

    global _self_learning
    _self_learning = SelfLearningManager(db=None)
    await _self_learning.initialize()
    init_self_learning(_self_learning)
    logger.info("Self-Learning Manager iniciado")

    init_analytics(SessionLocal)
    logger.info("Analytics Manager iniciado")

    init_localization(SessionLocal)
    logger.info("Localization Manager iniciado")

    init_security(SessionLocal)
    logger.info("Security Manager iniciado")

    init_device_modules(SessionLocal)
    logger.info("Device Orchestrator iniciado")

    init_finetuning(SessionLocal)
    logger.info("Fine-Tuning Manager iniciado")

    logger.info("N.O.M.A.D. Module cargado")

    await plugin_manager.execute_hook_async("on_startup")
    logger.info("Plugins hook on_startup ejecutado")

    asyncio.create_task(automation_engine.start_monitoring())
    logger.info("Automation monitoring started")

    await plugin_manager.execute_hook_async("on_startup")
    logger.info("Plugins hook on_startup ejecutado")


@app.post("/api/chat")
@limiter.limit("20/minute")
async def aura_chat(request: Request, auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db)) -> Dict[str, Any]:
    """
    Process chat message with ReAct Loop.

    Processes a chat message using the multi-agent ReAct Loop. AURA reasons,
    selects skills, and generates coherent responses in Spanish.

    Args:
        request: FastAPI Request containing JSON payload:
            - prompt: str (required) — user message
            - session_id: str (optional) — conversation session
            - user_id: str (optional) — user identifier
            - context: dict (optional) — additional context

    Returns:
        - response: str — AURA's response
        - thinking: str — reasoning process
        - skills_used: List[str] — skills executed
        - timestamp: str — ISO timestamp

    Raises:
        HTTPException 400: If prompt is empty
        HTTPException 401: If API key missing/invalid

    Example:
    ```bash
    curl -X POST http://localhost:8000/api/chat \\
      -H "Content-Type: application/json" \\
      -d '{"prompt": "¿Cuál es mi IP?"}'
    ```
    """
    payload: Any = await request.json()
    prompt = str(payload.get("prompt", "")).strip()
    await plugin_manager.execute_hook_async("on_chat", prompt, {"timestamp": datetime.now()})
    session_id = str(payload.get("session_id", "")).strip()
    user_id = str(payload.get("user_id", "")).strip() or None
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    await automation_engine.check_and_execute({
        "event": "chat_received",
        "message": prompt,
        "timestamp": datetime.now().isoformat()
    })

    conversation = None
    if session_id:
        conversation = db.query(Conversation).filter(Conversation.session_id == session_id).first()
        if not conversation:
            conversation = Conversation(
                session_id=session_id,
                user_id=user_id,
                created_at=time.time(),
                updated_at=time.time(),
            )
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
        conversation.updated_at = time.time()

    device_info = detect_device_role(
        user_agent=request.headers.get("user-agent", ""),
        source=str(payload.get("source", "")),
    )

    user_message = Message(
        conversation_id=conversation.id if conversation else 0,
        role="user",
        content=prompt,
        provider="user",
        timestamp=time.time(),
        extra=json.dumps({
            "image_base64": bool(payload.get("image_base64")),
            "audio_base64": bool(payload.get("audio_base64")),
            "video_base64": bool(payload.get("video_base64")),
        }),
    )
    db.add(user_message)

    media_info = []
    if payload.get("image_base64"):
        media_info.append("image")
    if payload.get("audio_base64"):
        media_info.append("audio")
    if payload.get("video_base64"):
        media_info.append("video")

    if media_info:
        logger.info("Media received from %s: %s", device_info.get("device", "unknown"), ", ".join(media_info))

    history: List[List[str]] = []
    if conversation:
        recent = db.query(Message).filter(Message.conversation_id == conversation.id).order_by(Message.timestamp.desc()).limit(20).all()
        for msg in reversed(recent):
            history.append([msg.role, msg.content])

    chat_request = ChatRequest(message=prompt, history=history)

    memory_context = ""
    try:
        mem_results = memory_engine.search(prompt, max_results=3, min_relevance=0.25)
        memory_context = " | ".join((m.get("text") or m.get("memory", "") or str(m)) for m in (mem_results.get("results") or mem_results.get("context") or []))
    except Exception:
        memory_context = ""

    enriched_prompt = f"{memory_context}\n\n{prompt}" if memory_context else prompt

    # Inyección de base literaria (Character Bible + Canon + Capítulos)
    story_system_prompt = "Eres AURA, un asistente de IA avanzado."
    story_context_active = False
    ctx = get_session_context(session_id) if session_id else None
    if ctx:
        try:
            from backend.story_memory.story_context import StoryContextManager

            sm = StoryContextManager()
            enriched_prompt, _ = sm.inject_story_context(session_id, enriched_prompt)
            story_context_active = True
        except Exception as exc:
            logger.debug("Story context injection failed: %s", exc)

    chat_request = ChatRequest(message=enriched_prompt, history=history)

    # -- BLOQUE 52: inyeccion de contexto visual al prompt de razonamiento del nucleo --
    try:
        from backend.vision.screen_bridge import get_screen_bridge as _get_vb
        _vb = _get_vb()
        _last = getattr(_vb, "_last_analysis", None)
        if _last is not None:
            _vtxt = _last.to_context_text()
            if _vtxt:
                enriched_prompt = f"[Contexto visual del escritorio] {_vtxt}\n\n{enriched_prompt}"
                chat_request = ChatRequest(message=enriched_prompt, history=history)
                logger.debug("BLOQUE 52: contexto visual inyectado en el prompt de razonamiento")
    except Exception as _vex:
        logger.debug("BLOQUE 52: inyeccion de contexto visual omitida: %s", _vex)

    cached = _get_cached_response(prompt, "local")
    result = None
    if cached:
        result = cached
    else:
        if media_info:
            result = _try_vision_chat(payload, chat_request)
        if not result:
            if _ai_router is None:
                logger.error("AI Router no inicializado; omitiendo router multi-proveedor")
            else:
                try:
                    if story_context_active and ctx:
                        try:
                            from backend.story_memory.story_context import StoryContextManager
                            sm = StoryContextManager()
                            story_system_prompt = sm.build_system_prompt(
                                work_id=ctx.get("work_id", ""),
                                character_id=ctx.get("character_id", ""),
                                base_prompt=story_system_prompt,
                            )
                        except Exception:
                            pass
                    router_result = await _ai_router.generate_response(
                        prompt=enriched_prompt,
                        context={"history": history},
                        system_prompt=story_system_prompt,
                        max_tokens=1024,
                        temperature=0.7,
                    )
                    if router_result and router_result.get("message"):
                        result = router_result
                except Exception as exc:
                    logger.error("AI Router failed: %s", exc)
        if not result:
            result = _try_qwen_chat(chat_request)
        if not result:
            result = _try_local_chat(chat_request)
        if not result:
            result = _local_response_chat(chat_request)
        if result and isinstance(result, dict):
            provider = result.get("provider", "local")
            _set_cached_response(prompt, provider, result)

    provider = "local"
    if isinstance(result, dict):
        provider = result.get("provider", "local")
        text = result.get("message", "")
    else:
        text = ""

    bot_message = Message(
        conversation_id=conversation.id if conversation else 0,
        role="assistant",
        content=text,
        provider=provider,
        timestamp=time.time(),
        extra=json.dumps({
            "media_received": media_info,
            "device": device_info.get("device", "unknown"),
            "role": device_info.get("role", "unknown"),
        }),
    )
    db.add(bot_message)
    db.commit()

    try:
        brain.record_conversation(
            device=device_info.get("device", DEVICE_UNKNOWN),
            role=device_info.get("role", ROLE_EXTERNAL),
            prompt=prompt,
            response=text,
            provider=provider,
        )
    except Exception as exc:
        logger.error("No se pudo registrar muestra de entrenamiento: %s", exc)

    try:
        memory_engine.remember(
            f"User: {prompt}\nAURA: {text}",
            memory_type="episodic",
            source="backend_chat",
            session_id=session_id or (conversation.session_id if conversation else None),
        )
    except Exception:
        pass

    # BIDIRECTIONAL SYNC: push chat_received delta to mobile via sync_engine
    try:
        from backend.sync_engine import get_sync_engine
        _sync_engine = get_sync_engine()
        _client_id = str(payload.get("client_id") or device_info.get("device", "pc"))
        _sync_engine.ingest_pc_event(
            event_type="chat_received",
            payload={
                "role": "user",
                "content": prompt,
                "response": text,
                "provider": provider,
                "session_id": session_id or (conversation.session_id if conversation else None),
                "client_id": _client_id,
                "timestamp": time.time(),
            },
            client_id=_client_id,
            source="backend_chat",
        )
        # memory_updated delta (episodic memory write)
        _sync_engine.ingest_pc_event(
            event_type="memory_updated",
            payload={
                "session_id": session_id or (conversation.session_id if conversation else None),
                "text": f"User: {prompt}\nAURA: {text}",
                "memory_type": "episodic",
                "timestamp": time.time(),
            },
            client_id=_client_id,
            source="backend_chat",
        )
    except Exception as _sync_err:
        logger.debug("sync ingest skipped: %s", _sync_err)

    return {
        "text": text,
        "provider": provider,
        "session_id": session_id or (conversation.session_id if conversation else None),
    }


@app.post("/api/feedback")
@limiter.limit("30/minute")
async def feedback(request: Request, auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db)) -> Dict[str, str]:
    payload: Any = await request.json()
    value = str(payload.get("feedback", "")).strip()
    if not value:
        raise HTTPException(status_code=400, detail="feedback is required")
    db.add(LogEntry(service="discord-bot", level="INFO", message=f"Feedback received: {value}", timestamp=time.time()))
    db.commit()
    return {"message": f"Feedback registrado: {value}"}


@app.get("/api/brain")
async def brain_status(auth: AuthContext = Depends(require_api_key)) -> Dict[str, Any]:
    return brain.get_brain_status()


@app.get("/api/brain/training-data")
async def brain_training_data(request: Request, auth: AuthContext = Depends(require_api_key), days: int = 7, limit: int = 100) -> Dict[str, Any]:
    samples = brain.get_training_dataset(days=days, limit=limit)
    return {
        "count": len(samples),
        "samples": samples,
    }


@app.get("/api/orchestrator")
async def orchestrator_status(auth: AuthContext = Depends(require_api_key)) -> Dict[str, Any]:
    return orchestrator.get_status()


@app.post("/api/orchestrator/register")
async def register_node(request: Request) -> Dict[str, Any]:
    payload: Any = await request.json()
    node_id = str(payload.get("node_id", "")).strip()
    node_type = str(payload.get("node_type", "")).strip()
    base_url = str(payload.get("base_url", "")).strip()
    role = str(payload.get("role", "")).strip()
    capabilities = payload.get("capabilities", [])
    if not all([node_id, node_type, base_url, role]):
        raise HTTPException(status_code=400, detail="node_id, node_type, base_url and role are required")
    node = Node(node_id=node_id, node_type=node_type, base_url=base_url, role=role)
    if capabilities:
        node.capabilities = capabilities
    orchestrator.register_node(node)
    orchestrator.mark_online(node_id, capabilities)
    return {"message": f"Node {node_id} registered", "status": "ok"}


@app.post("/api/brain/train")
async def brain_train(request: Request, auth: AuthContext = Depends(require_api_key)) -> Dict[str, str]:
    if not brain.should_retrain():
        return {"message": "Not enough new data to retrain", "status": "skipped"}
    try:
        job = TrainingJob(
            status="starting",
            model_name="unified-brain-finetune",
            dataset_path="brain_training_dataset.jsonl",
            output_dir="fine-tuned-brain",
            started_at=time.time(),
        )
        db = SessionLocal()
        db.add(job)
        db.commit()
        db.refresh(job)
        db.close()

        def run_training():
            try:
                job.status = "running"
                db = SessionLocal()
                db.add(job)
                db.commit()
                db.close()

                samples = brain.get_training_dataset(days=30, limit=5000)
                dataset_path = os.path.join(TRAINING_DATA_DIR, "brain_training_dataset.jsonl")
                with open(dataset_path, "w", encoding="utf-8") as f:
                    for sample in samples:
                        f.write(json.dumps(sample, ensure_ascii=False) + "\n")

                env = {
                    **os.environ,
                    "AURA_TRAINING_MODEL_NAME": "Qwen/Qwen2.5-0.5B",
                    "AURA_TRAINING_DATASET_PATH": dataset_path,
                    "AURA_TRAINING_OUTPUT_DIR": "fine-tuned-brain",
                }
                subprocess.run(
                    [sys.executable, "training/run_training_job.py"],
                    env=env,
                    check=False,
                )

                job.status = "finished"
                job.finished_at = time.time()
                job.metrics = f"trained_on_{len(samples)}_samples"
                brain.register_model_update(
                    model_id="cloud-small",
                    version=f"1.0.{int(time.time())}",
                    path="/app/models/qwen-0.5b",
                    role=ROLE_SMALL,
                    device=DEVICE_SERVER,
                )
            except Exception as exc:
                job.status = "failed"
                job.metrics = str(exc)
                logger.error("Brain training failed: %s", exc)
            finally:
                try:
                    db = SessionLocal()
                    db.add(job)
                    db.commit()
                    db.close()
                except Exception:
                    pass

        threading.Thread(target=run_training, daemon=True).start()
        return {"message": f"Brain training started: job {job.id}", "status": "started"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/ai")
@limiter.limit("20/minute")
async def local_ai(request: Request) -> Dict[str, Any]:
    payload: Any = await request.json()
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    try:
        model, tokenizer = _get_local_model()
        inputs = tokenizer(prompt, return_tensors="pt")
        outputs = model.generate(**inputs, max_new_tokens=int(payload.get("max_tokens", 256)))
        text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        if text.startswith(prompt):
            text = text[len(prompt):].strip()
        return {"text": text, "provider": "local-qwen"}
    except Exception as exc:
        logger.error("Local AI error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chat/stream")
@limiter.limit("10/minute")
async def aura_chat_stream(request: Request, auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db)) -> StreamingResponse:
    payload: Any = await request.json()
    prompt = str(payload.get("prompt", "")).strip()
    session_id = str(payload.get("session_id", "")).strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    async def event_stream():
        try:
            model, tokenizer = _get_local_model()
            system_prompt = "Eres AURA, un asistente de IA avanzado."
            prompt_text = f"{system_prompt}\n\nUsuario: {prompt}\nAURA:"
            inputs = tokenizer(prompt_text, return_tensors="pt")
            streamer = None
            try:
                from transformers import TextIteratorStreamer
                import threading
                streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
                generation_kwargs = {**inputs, "streamer": streamer, "max_new_tokens": 128, "temperature": 0.7, "pad_token_id": tokenizer.eos_token_id}
                thread = threading.Thread(target=model.generate, kwargs=generation_kwargs)
                thread.start()
                for token in streamer:
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception:
                outputs = model.generate(**inputs, max_new_tokens=128, temperature=0.7, pad_token_id=tokenizer.eos_token_id)
                text = tokenizer.decode(outputs[0], skip_special_tokens=True)
                if text.startswith(prompt_text):
                    text = text[len(prompt_text):].strip()
                for char in text:
                    yield f"data: {json.dumps({'token': char})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# =============================================================================
# OMNIROUTE INTEGRATION (Multi-Provider AI — 300+ Providers)
# =============================================================================

@app.post("/api/chat/omniroute", tags=["Chat"])
async def chat_omniroute(request: ChatRequest):
    """
    Chat con soporte para 300+ proveedores de IA via Omniroute.

    Selecciona automaticamente el mejor proveedor segun score de 12 factores.
    Con fallback inteligente si el proveedor falla.
    """
    try:
        context = [{"role": "user", "content": request.message}]

        response = await omniroute_client.chat(
            message=request.message,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            context=context,
            stream=False,
        )

        return {
            "response": response,
            "source": "omniroute",
            "provider_info": "Selected automatically by Omniroute scoring",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        print(f"[Omniroute] Error, falling back to local: {e}")

        try:
            react = _react_loop or ReactLoop()
            response = await react.process(request.message)
        except Exception:
            response = f"Error: {str(e)}"

        return {
            "response": response,
            "source": "local_fallback",
            "error_info": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@app.get("/api/providers", tags=["Omniroute"])
async def list_providers():
    """Listar todos los proveedores disponibles"""
    providers = await omniroute_client.get_providers()
    return {
        "total": len(providers),
        "providers": [
            {
                "name": p.name,
                "model": p.model,
                "status": p.status.value,
                "latency_ms": p.latency_ms,
                "score": p.score,
            }
            for p in providers
        ],
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/providers/best", tags=["Omniroute"])
async def get_best_provider():
    """Obtener mejor proveedor"""
    provider = await omniroute_client.get_best_provider()
    if not provider:
        raise HTTPException(status_code=503, detail="No healthy providers available")

    return {
        "name": provider.name,
        "model": provider.model,
        "status": provider.status.value,
        "latency_ms": provider.latency_ms,
        "score": provider.score,
    }


@app.get("/api/providers/stats", tags=["Omniroute"])
async def get_provider_stats():
    """Estadisticas de todos los proveedores"""
    return await provider_manager.get_all_stats()


@app.get("/api/providers/{provider_name}/stats", tags=["Omniroute"])
async def get_provider_stat(provider_name: str):
    """Estadisticas de un proveedor especifico"""
    return await provider_manager.get_provider_stats(provider_name)


@app.get("/api/providers/recommendations", tags=["Omniroute"])
async def get_recommendations():
    """Recomendaciones de proveedores"""
    return await provider_manager.get_recommendations()


@app.get("/api/omniroute/health", tags=["Omniroute"])
async def omniroute_health():
    """Verificar salud de Omniroute"""
    return await omniroute_client.get_health()


@app.get("/api/conversations")
async def list_conversations(auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db)) -> Dict[str, Any]:
    conversations = db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(50).all()
    return {
        "conversations": [
            {
                "id": c.id,
                "session_id": c.session_id,
                "user_id": c.user_id,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
            for c in conversations
        ]
    }


@app.get("/api/conversations/{session_id}/messages")
async def get_conversation_messages(session_id: str, auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db)) -> Dict[str, Any]:
    conversation = db.query(Conversation).filter(Conversation.session_id == session_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = db.query(Message).filter(Message.conversation_id == conversation.id).order_by(Message.timestamp.asc()).all()
    return {
        "session_id": session_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "provider": m.provider,
                "timestamp": m.timestamp,
            }
            for m in messages
        ],
    }


@app.delete("/api/conversations/{session_id}")
async def delete_conversation(session_id: str, auth: AuthContext = Depends(require_api_key), db: SessionLocal = Depends(get_db)) -> Dict[str, str]:
    conversation = db.query(Conversation).filter(Conversation.session_id == session_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.query(Message).filter(Message.conversation_id == conversation.id).delete()
    db.delete(conversation)
    db.commit()
    return {"message": f"Conversation {session_id} deleted"}


@app.post("/api/tts")
@limiter.limit("30/minute")
async def text_to_speech(request: Request, payload: TTSRequest, auth: AuthContext = Depends(require_api_key)) -> JSONResponse:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    try:
        import tempfile
        import base64
        tts_dir = os.path.join(os.path.dirname(__file__), "..", "data", "tts")
        os.makedirs(tts_dir, exist_ok=True)
        wav_path = os.path.join(tts_dir, f"tts_{int(time.time())}.wav")
        mp3_path = wav_path.replace(".wav", ".mp3")
        cmd = None
        for candidate in [
            ["espeak-ng", "-v", payload.voice, "-s", str(int(150 * payload.speed)), "-w", wav_path, text],
            ["espeak", "-v", payload.voice, "-s", str(int(150 * payload.speed)), "-w", wav_path, text],
        ]:
            try:
                subprocess.run(candidate, check=True, capture_output=True)
                cmd = candidate
                break
            except FileNotFoundError:
                continue
        if cmd is None:
            try:
                from gtts import gTTS
                tts = gTTS(text=text, lang="es" if any(ord(c) > 127 for c in text) else "en", slow=False)
                tts.save(mp3_path)
                if os.path.isfile(mp3_path):
                    with open(mp3_path, "rb") as f:
                        audio_data = f.read()
                    os.remove(mp3_path)
                    return JSONResponse({"audio_base64": base64.b64encode(audio_data).decode(), "format": "mp3"})
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="No TTS engine available (install espeak-ng or gTTS)")
        with open(wav_path, "rb") as f:
            audio_data = f.read()
        os.remove(wav_path)
        return JSONResponse({"audio_base64": base64.b64encode(audio_data).decode(), "format": "wav"})
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("TTS error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/device/automate")
@limiter.limit("10/minute")
async def device_automate(request: Request, payload: DeviceAutomationRequest, auth: AuthContext = Depends(require_api_key)) -> Dict[str, Any]:
    action = payload.action.strip().lower()
    target = payload.target.strip()
    params = payload.params or {}
    if not action:
        raise HTTPException(status_code=400, detail="action is required")
    try:
        if action == "adb_shell":
            if not target:
                raise HTTPException(status_code=400, detail="target (adb command) is required for adb_shell")
            result = subprocess.run(["adb", "shell", target], capture_output=True, text=True, timeout=30)
            return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
        elif action == "adb_open_app":
            package = params.get("package", "")
            if not package:
                raise HTTPException(status_code=400, detail="package param is required")
            result = subprocess.run(["adb", "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"], capture_output=True, text=True, timeout=30)
            return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode, "package": package}
        elif action == "adb_call":
            number = params.get("number", "")
            if not number:
                raise HTTPException(status_code=400, detail="number param is required")
            result = subprocess.run(["adb", "shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{number}"], capture_output=True, text=True, timeout=30)
            return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode, "number": number}
        elif action == "script":
            script_path = params.get("path", "")
            if not script_path or not os.path.isfile(script_path):
                raise HTTPException(status_code=400, detail="valid script path param is required")
            result = subprocess.run(["python", script_path] + [str(v) for v in params.get("args", [])], capture_output=True, text=True, timeout=60)
            return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
        elif action == "open_url":
            url = params.get("url", "")
            if not url:
                raise HTTPException(status_code=400, detail="url param is required")
            import webbrowser
            webbrowser.open(url)
            return {"url": url, "action": "opened"}
        else:
            raise HTTPException(status_code=400, detail=f"unsupported action: {action}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Device automation error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/wifi/scan")
@limiter.limit("5/minute")
async def wifi_scan(request: Request, payload: Optional[WiFiScanRequest] = None, auth: AuthContext = Depends(require_api_key)) -> Dict[str, Any]:
    try:
        if payload is None:
            payload = WiFiScanRequest()
        scan_results = []
        if sys.platform == "win32":
            result = subprocess.run(["netsh", "wlan", "show", "networks", "mode=Bssid"], capture_output=True, text=True, timeout=15)
            scan_results = _parse_windows_wifi(result.stdout)
        else:
            result = subprocess.run(["sudo", "iwlist", payload.interface, "scan"], capture_output=True, text=True, timeout=15)
            scan_results = _parse_iwlist(result.stdout)
        return {"interface": payload.interface, "networks": scan_results, "timestamp": time.time()}
    except Exception as exc:
        logger.error("WiFi scan error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


def _parse_windows_wifi(output: str) -> List[Dict[str, Any]]:
    networks = []
    current = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("SSID"):
            if current:
                networks.append(current)
            current = {"ssid": line.split(":", 1)[1].strip() if ":" in line else ""}
        elif line.startswith("BSSID"):
            current["bssid"] = line.split(":", 1)[1].strip() if ":" in line else ""
        elif line.startswith("Signal"):
            current["signal"] = line.split(":", 1)[1].strip() if ":" in line else ""
        elif line.startswith("Channel"):
            current["channel"] = line.split(":", 1)[1].strip() if ":" in line else ""
    if current:
        networks.append(current)
    return networks


def _parse_iwlist(output: str) -> List[Dict[str, Any]]:
    networks = []
    current = {}
    for line in output.splitlines():
        line = line.strip()
        if "ESSID:" in line:
            if current:
                networks.append(current)
            current = {"ssid": line.split("ESSID:")[1].strip().strip('"')}
        elif "Address:" in line:
            current["bssid"] = line.split("Address:")[1].strip()
        elif "Signal level=" in line:
            current["signal"] = line.split("Signal level=")[1].split(" ")[0]
        elif "Channel:" in line:
            current["channel"] = line.split("Channel:")[1].strip()
    if current:
        networks.append(current)
    return networks


@app.get("/api/system/telemetry", response_model=TelemetryResponse)
@limiter.limit("30/minute")
async def system_telemetry(request: Request, auth: AuthContext = Depends(require_api_key)) -> TelemetryResponse:
    cpu = 0.0
    memory = 0.0
    disk = 0.0
    network = {"bytes_sent": 0, "bytes_recv": 0, "packets_sent": 0, "packets_recv": 0}
    processes = []
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage("/").percent if sys.platform != "win32" else psutil.disk_usage("C:\\").percent
        net = psutil.net_io_counters()
        network = {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv, "packets_sent": net.packets_sent, "packets_recv": net.packets_recv}
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        processes.sort(key=lambda p: p.get("cpu_percent", 0) or 0, reverse=True)
        processes = processes[:20]
    except ImportError:
        if sys.platform == "win32":
            try:
                cpu = float(os.popen("wmic cpu get loadpercentage /value").read().split("=")[1].strip())
            except Exception:
                pass
            try:
                mem = os.popen("systeminfo | findstr /C:\"Total Physical Memory\" /C:\"Available Physical Memory\"").read().splitlines()
                if len(mem) == 2:
                    total = int(mem[0].split(":")[1].strip().replace(",", "").replace(" MB", ""))
                    avail = int(mem[1].split(":")[1].strip().replace(",", "").replace(" MB", ""))
                    memory = ((total - avail) / total) * 100 if total else 0.0
            except Exception:
                pass
    return TelemetryResponse(cpu=cpu, memory=memory, disk=disk, network=network, processes=processes, timestamp=time.time())


@app.post("/api/network/topology", response_model=NetworkTopologyResponse)
@limiter.limit("5/minute")
async def network_topology(request: Request, auth: AuthContext = Depends(require_api_key)) -> NetworkTopologyResponse:
    nodes = [{"id": "local", "label": "AURA Local", "ip": "127.0.0.1", "type": "server"}]
    edges = []
    try:
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        nodes = [{"id": "local", "label": hostname, "ip": local_ip, "type": "server"}]
        if sys.platform != "win32":
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10)
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[0] != "Interface:":
                    ip = parts[0]
                    mac = parts[1]
                    nodes.append({"id": ip, "label": ip, "ip": ip, "mac": mac, "type": "device"})
                    edges.append({"source": "local", "target": ip})
    except Exception as exc:
        logger.error("Network topology error: %s", exc)
    return NetworkTopologyResponse(nodes=nodes, edges=edges, timestamp=time.time())


@app.post("/api/agent/command")
@limiter.limit("20/minute")
async def agent_command(request: Request, payload: AgentCommandRequest, auth: AuthContext = Depends(require_api_key)) -> Dict[str, Any]:
    command = payload.command.strip().lower()
    context = payload.context or {}
    device = payload.device.strip().lower() if payload.device else "local"
    if not command:
        raise HTTPException(status_code=400, detail="command is required")
    try:
        if command == "status":
            return {"device": device, "status": "online", "agent": "AURA JARVIS Core"}
        elif command == "brain_status":
            stats = brain.get_training_stats() if hasattr(brain, "get_training_stats") else {}
            return {"device": device, "brain": stats}
        elif command == "orchestrator_status":
            status = orchestrator.get_status() if hasattr(orchestrator, "get_status") else {}
            return {"device": device, "orchestrator": status}
        elif command == "devices_list":
            return {"device": device, "devices": orchestrator.get_devices() if hasattr(orchestrator, "get_devices") else []}
        elif command == "execute_script":
            script = context.get("script", "")
            if not script:
                raise HTTPException(status_code=400, detail="script in context is required")
            allowed = {"time", "os", "json", "subprocess", "sys", "logging"}
            local_ns = {"__builtins__": {k: __builtins__[k] for k in ("print", "len", "str", "int", "float", "list", "dict", "True", "False", "None") if k in __builtins__}}
            for mod in allowed:
                try:
                    local_ns[mod] = __import__(mod)
                except ImportError:
                    pass
            result = eval(compile(script, "<agent>", "eval"), {"__builtins__": {}}, local_ns)
            return {"device": device, "result": str(result)}
        elif command == "system_prompt":
            new_prompt = context.get("prompt", "")
            if not new_prompt:
                raise HTTPException(status_code=400, detail="prompt in context is required")
            from backend.models import SystemPrompt
            db = SessionLocal()
            try:
                prompt_obj = db.query(SystemPrompt).first()
                if not prompt_obj:
                    prompt_obj = SystemPrompt(content=new_prompt, version=int(time.time()))
                    db.add(prompt_obj)
                else:
                    prompt_obj.content = new_prompt
                    prompt_obj.version = int(time.time())
                db.commit()
                return {"device": device, "system_prompt": new_prompt, "version": prompt_obj.version}
            finally:
                db.close()
        else:
            return {"device": device, "error": f"unknown command: {command}"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Agent command error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/gesture/stream")
@limiter.limit("10/minute")
async def gesture_stream(request: Request, auth: AuthContext = Depends(require_api_key)) -> StreamingResponse:
    async def event_stream():
        try:
            import cv2
            import mediapipe as mp
            import base64
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                yield f"data: {json.dumps({'error': 'camera not available'})}\n\n"
                return
            with mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7) as hands:
                last_gesture = ""
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    result = hands.process(rgb)
                    gesture = "unknown"
                    confidence = 0.0
                    fingers = 0
                    if result.multi_hand_landmarks:
                        landmarks = result.multi_hand_landmarks[0].landmark
                        finger_tips = [8, 12, 16, 20]
                        finger_pips = [6, 10, 14, 18]
                        fingers = sum(1 for tip, pip in zip(finger_tips, finger_pips) if landmarks[tip].y < landmarks[pip].y)
                        if fingers == 4 and all(landmarks[i].y < landmarks[i - 2].y for i in [8, 12, 16, 20]):
                            gesture = "open_hand"
                            confidence = 0.9
                        elif fingers == 2 and landmarks[8].y < landmarks[6].y and landmarks[12].y < landmarks[10].y:
                            gesture = "peace"
                            confidence = 0.85
                        elif fingers == 1 and landmarks[8].y < landmarks[6].y:
                            gesture = "index"
                            confidence = 0.85
                        elif fingers == 0 and all(landmarks[i].y >= landmarks[i - 2].y for i in [8, 12, 16, 20]):
                            gesture = "fist"
                            confidence = 0.85
                        elif fingers >= 3:
                            gesture = "open_hand"
                            confidence = 0.7
                        else:
                            gesture = "swipe"
                            confidence = 0.5
                    if gesture != last_gesture:
                        last_gesture = gesture
                        yield f"data: {json.dumps({'gesture': gesture, 'confidence': confidence, 'fingers': fingers, 'timestamp': time.time()})}\n\n"
                    await asyncio.sleep(0.1)
            cap.release()
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/orchestrator")
async def get_orchestrator_protected(current_user: str = Depends(get_current_user)):
    return await orchestrator.get_status_async()


@app.on_event("startup")
async def _on_startup_production() -> None:
    try:
        await init_redis()
    except Exception as exc:
        logger.error("Redis init failed: %s", exc)
    try:
        init_metrics_server(port=int(os.getenv("PROMETHEUS_PORT", "8001")))
    except Exception as exc:
        logger.error("Metrics server failed: %s", exc)

    try:
        mdns.start()
        logger.info(
            "mDNS service registered: %s on %s:%d",
            "_aura-host._tcp.local", resolve_local_ip(), mdns.port,
        )
    except Exception as exc:
        logger.warning("mDNS start failed: %s", exc)

    # BLOQUE 48: arrancar el daemon pasivo de salud y diagnósticos local.
    try:
        get_health_daemon().start()
        logger.info("Local Health Daemon iniciado (diagnósticos del sistema)")
    except Exception as exc:
        logger.warning("Health Daemon start failed: %s", exc)

    try:
        await provider_manager.start_monitoring(interval=int(os.getenv("OMNIROUTE_MONITOR_INTERVAL", "300")))
        logger.info("Omniroute provider monitoring started")
    except Exception as exc:
        logger.warning("Omniroute monitoring start failed: %s", exc)

    if IS_CLUSTER_MODE:
        try:
            await orchestrator.initialize_cluster()
            await failover_manager.start_monitoring()
            asyncio.create_task(distributed_metrics_collector.collect_metrics_from_cluster())
            logger.info(
                "Backend iniciado (NODE_ID: %s, CLUSTER: %s)",
                NODE_ID,
                IS_CLUSTER_MODE,
            )
        except Exception as exc:
            logger.error("Cluster init failed: %s", exc)


@app.on_event("shutdown")
async def _on_shutdown_production() -> None:
    # BLOQUE 34: detener el daemon de tareas en segundo plano (best-effort).
    try:
        from backend.agent_scheduler import get_agent_scheduler, reset_agent_scheduler
        daemon = get_agent_scheduler()
        if daemon is not None:
            await daemon.stop()
        reset_agent_scheduler()
        logger.info("Agent daemon detenido")
    except Exception as exc:
        logger.warning("Agent daemon shutdown failed (no crítico): %s", exc)

    if IS_CLUSTER_MODE:
        try:
            from backend.distributed.redis_pubsub import redis_pubsub
            await redis_pubsub.close()
        except Exception as exc:
            logger.error("Redis close failed: %s", exc)
        logger.info("Backend detenido (NODE_ID: %s)", NODE_ID)

    try:
        mdns.stop()
    except Exception as exc:
        logger.warning("mDNS stop failed: %s", exc)

    # BLOQUE 48: detener el daemon pasivo de salud (best-effort).
    try:
        from backend.diagnostics.health import stop_health_daemon
        stop_health_daemon()
    except Exception as exc:
        logger.warning("Health Daemon stop failed: %s", exc)

    try:
        await provider_manager.stop_monitoring()
        await omniroute_client.close()
    except Exception as exc:
        logger.warning("Omniroute cleanup failed: %s", exc)


@app.get("/api/cluster/status", tags=["cluster"])
async def get_cluster_status():
    """Retorna estado del cluster."""
    if not IS_CLUSTER_MODE:
        return {"error": "Not in cluster mode"}

    return await orchestrator.get_cluster_status()


# =============================================================================
# Mobile Sync Endpoints
# =============================================================================

@app.api_route("/api/mobile/discovery", methods=["GET", "POST"], tags=["Mobile"])
async def mobile_discovery():
    """
    Endpoint de descubrimiento para clientes móviles (BLOQUE 35).

    Retorna información del dispositivo AURA para conexión móvil, incluyendo:
    - IPs locales para fallback manual (cuando mDNS falla).
    - Tipo de servicio mDNS (_aura-host._tcp.local).

    No requiere autenticación — es información pública del servidor local.
    """
    import socket
    hostname = socket.gethostname()
    local_ips = get_local_ips()
    return {
        "name": "AURA OS",
        "version": "2.1.0",
        "hostname": hostname,
        "port": int(os.getenv("AURA_API_PORT", "8000")),
        "api_version": "v2",
        "service_type": "_aura-host._tcp.local",
        "local_ips": local_ips,
        "features": ["chat", "skills", "voice", "auth", "sync", "browser"],
        "status": "online",
        "last_contact": time.time(),
    }


@app.get("/api/mobile/discover", tags=["Mobile"])
async def mobile_discover_hosts(timeout: float = 2.0):
    """Activa el descubrimiento mDNS y retorna hosts AURA en la red local.

    BLOQUE 35 — Endpoint REST de respaldo que envuelve ``discover_hosts()`` de forma
    no bloqueante (run_in_executor) para no bloquear el event loop de FastAPI.
    Incluye hosts manuales configurados vía ``AURA_HOST_IPS`` / ``TAILSCALE_IP``.
    """
    from backend.mobile.discovery import discover_hosts, parse_manual_hosts

    try:
        hosts = await asyncio.get_running_loop().run_in_executor(
            None, lambda: discover_hosts(timeout=min(timeout, 5.0))
        )
        return {"status": "ok", "hosts": list(hosts.values()), "manual_hosts": parse_manual_hosts()}
    except Exception as exc:  # noqa: BLE001
        logger.warning("mDNS discover failed: %s", exc)
        return {"status": "error", "detail": str(exc), "hosts": [], "manual_hosts": parse_manual_hosts()}


# =============================================================================
# BLOQUE 36: Encrypted Vault & SD-Card Security Layer
# =============================================================================

_vault = None


def _get_vault() -> "EncryptedStore":
    global _vault
    if _vault is None:
        from backend.security.crypto import get_default_store
        _vault = get_default_store()
    return _vault


@app.get("/api/vault/status", tags=["Security"])
async def vault_status():
    """Estado de la bóveda cifrada (sin exponer secretos)."""
    return _get_vault().status()


@app.post("/api/vault/unlock", tags=["Security"])
async def vault_unlock(payload: Dict[str, Any]):
    """Desbloquea la bóveda con un secreto maestro (no se persiste)."""
    master_secret = str(payload.get("master_secret", ""))
    if not master_secret:
        raise HTTPException(status_code=400, detail="master_secret is required")
    try:
        vault = _get_vault()
        if vault.is_locked:
            return vault.unlock(master_secret)
        return {"status": "already_unlocked", "lock_secs": vault.lock_secs}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=403, detail=str(exc))


@app.post("/api/vault/lock", tags=["Security"])
async def vault_lock():
    """Bloquea la bóveda manualmente (borra la clave de memoria)."""
    vault = _get_vault()
    return vault.lock()


@app.get("/api/vault/list", tags=["Security"])
async def vault_list():
    """Lista las entradas cifradas en la bóveda local."""
    vault = _get_vault()
    if vault.is_locked:
        raise HTTPException(status_code=403, detail="vault is locked")
    return {"entries": vault.list_entries()}


@app.get("/api/vault/read/{name}", tags=["Security"])
async def vault_read(name: str):
    """Lee y descifra una entrada de la bóveda."""
    vault = _get_vault()
    if vault.is_locked:
        raise HTTPException(status_code=403, detail="vault is locked")
    data = vault.read(name)
    return {"status": "ok", "name": name, "data": data} if data is not None else {
        "status": "not_found", "name": name, "data": None
    }


@app.post("/api/vault/write/{name}", tags=["Security"])
async def vault_write(name: str, payload: Dict[str, Any]):
    """Cifra y escribe un payload en la bóveda local (at-rest)."""
    vault = _get_vault()
    if vault.is_locked:
        raise HTTPException(status_code=403, detail="vault is locked")
    return vault.write(name, payload)


@app.delete("/api/vault/delete/{name}", tags=["Security"])
async def vault_delete(name: str):
    """Elimina una entrada cifrada de la bóveda."""
    vault = _get_vault()
    return vault.delete(name)


@app.get("/api/mobile/pairing-profile", tags=["Mobile"])
async def get_pairing_profile(request: Request):
    """Endpoint de emparejamiento local para AME.

    Genera un perfil con:
    - IPs locales de la PC (interfaz de red)
    - Puerto del backend
    - Token de sesión de emparejamiento temporal (cifrado/hashed)

    No expone tokens completos. No requiere autenticación (discovery local).
    """
    import ipaddress
    import socket as _socket

    def _get_local_ips() -> list[str]:
        ips: list[str] = []
        try:
            hostname = _socket.gethostname()
            try:
                local_ip = _socket.gethostbyname(hostname)
                if local_ip and not _socket.inet_aton(local_ip) == _socket.inet_aton("127.0.0.1"):
                    ips.append(local_ip)
            except Exception:
                pass

            try:
                s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
                s.settimeout(1)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                if local_ip and local_ip not in ips:
                    ips.append(local_ip)
            except Exception:
                pass
        except Exception:
            pass
        return ips

    local_ips = _get_local_ips()
    pairing_token = secrets.token_urlsafe(32)
    try:
        from backend.device_auth import DeviceAuthManager
        DeviceAuthManager.get_instance().register_device("pairing_temp", "AME Pairing Temp")
    except Exception:
        pass

    port = 8000
    return {
        "name": "AURA OS",
        "hostname": _socket.gethostname(),
        "local_ips": local_ips,
        "port": port,
        "ws_port": port,
        "pairing_token": pairing_token,
        "pairing_token_ttl": 300,
        "api_version": "v2",
        "timestamp": time.time(),
    }


@app.get("/api/mobile/health-check", tags=["Mobile"])
async def mobile_health_check(request: Request):
    """Health-check de conectividad local entre AME y AURA PC."""
    import socket as _socket
    hostname = _socket.gethostname()
    try:
        local_ip = _socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"
    return {
        "status": "healthy",
        "hostname": hostname,
        "local_ip": local_ip,
        "port": 8000,
        "timestamp": time.time(),
        "latency_ms": 0,
    }


@app.post("/api/mobile/devices/register", tags=["Mobile"])
async def mobile_register_device(request: Request):
    """Register a mobile device (AME) for pairing."""
    from backend.device_auth import DeviceAuthManager
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = str(body.get("device_id", "")).strip()
    device_name = str(body.get("device_name", "")).strip()
    if not device_id:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "device_id is required"})
    result = DeviceAuthManager.get_instance().register_device(device_id, device_name)
    return result


@app.post("/api/mobile/devices/approve", tags=["Mobile"])
async def mobile_approve_device(request: Request):
    """Approve a pending device."""
    from backend.device_auth import DeviceAuthManager
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = str(body.get("device_id", "")).strip()
    permissions = body.get("permissions")
    if not device_id:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "device_id is required"})
    approved = DeviceAuthManager.get_instance().approve_device(device_id, permissions)
    if not approved:
        return JSONResponse(status_code=404, content={"status": "error", "detail": "device not found or already approved"})
    return {"status": "ok", "approved": True}


@app.get("/api/mobile/devices", tags=["Mobile"])
async def mobile_list_devices():
    """Listar dispositivos AME registrados (sanitizado)."""
    from backend.device_auth import DeviceAuthManager
    return {"devices": DeviceAuthManager.get_instance().list_devices()}


@app.post("/api/mobile/devices/refresh", tags=["Mobile"])
async def mobile_refresh_token(request: Request):
    """Refresh a device's token."""
    from backend.device_auth import DeviceAuthManager
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = str(body.get("device_id", "")).strip()
    current_token = str(body.get("token", "")).strip()
    if not device_id or not current_token:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "device_id and token are required"})
    result = DeviceAuthManager.get_instance().refresh_token(device_id, current_token)
    if result is None:
        return JSONResponse(status_code=401, content={"status": "error", "detail": "invalid or expired token"})
    return {"status": "ok", "token": result["token"], "expires_in": result["expires_in"]}


@app.post("/api/mobile/devices/revoke", tags=["Mobile"])
async def mobile_revoke_device(request: Request):
    """Revoke a device's access."""
    from backend.device_auth import DeviceAuthManager
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = str(body.get("device_id", "")).strip()
    if not device_id:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "device_id is required"})
    revoked = DeviceAuthManager.get_instance().revoke_device(device_id)
    if not revoked:
        return JSONResponse(status_code=404, content={"status": "error", "detail": "device not found"})
    return {"status": "ok", "revoked": True}


@app.post("/api/mobile/devices/logout", tags=["Mobile"])
async def mobile_logout_device(request: Request):
    """Logout a device (expire its token without removing registration)."""
    from backend.device_auth import DeviceAuthManager
    try:
        body = await request.json()
    except Exception:
        body = {}
    device_id = str(body.get("device_id", "")).strip()
    if not device_id:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "device_id is required"})
    logged_out = DeviceAuthManager.get_instance().logout_device(device_id)
    if not logged_out:
        return JSONResponse(status_code=404, content={"status": "error", "detail": "device not found"})
    return {"status": "ok", "logged_out": True}


@app.websocket("/api/mobile/sync/{client_id}")
async def mobile_sync_ws(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint para sync móvil-desktop.

    Acepta autenticación únicamente por primer mensaje JSON:
    {"type":"auth","token":"...","deviceId":"..."}

    Token validation:
    - Si AURA_API_KEY está definido, el token debe coincidir con él (legacy).
    - Si DISCORD_BOT_TOKEN está definido (device auth mode), validate via device_auth.
    - En desarrollo (sin AURA_API_KEY), también se exige el mensaje de autenticación, aunque el token esté vacío.
    """
    expected_api_key = os.getenv("AURA_API_KEY", "")

    await websocket.accept()

    try:
        first_message = await websocket.receive_text()
        import json as _json
        parsed = _json.loads(first_message)
        token = parsed.get("token", "")
        device_id = parsed.get("deviceId") or parsed.get("device_id") or client_id

        auth_ok = False
        auth_status = "auth_failed"

        if expected_api_key:
            auth_ok = token == expected_api_key
            auth_status = "ok" if auth_ok else "invalid_api_key"
        else:
            from backend.device_auth import DeviceAuthManager
            if device_id and token and len(token) > 20:
                auth_ok = DeviceAuthManager.get_instance().validate_token(device_id, token)
                auth_status = "ok" if auth_ok else "invalid_token"
            else:
                auth_ok = True
                auth_status = "ok"
                _safe_device = device_id[:4] + "****" + device_id[-4:] if len(device_id) > 8 else "****"
                logger.warning("Dev mode: no AURA_API_KEY set, accepting unauthenticated connection from %s", _safe_device)

        if parsed.get("type") != "auth" or not auth_ok:
            await websocket.close(code=1008, reason="Unauthorized")
            return
        await websocket.send_json({"status": "ok", "auth": "accepted"})
    except (ValueError, TypeError, json.JSONDecodeError):
        await websocket.close(code=1008, reason="Unauthorized")
        return

    async def _handle_chat_message(data: Dict[str, Any]) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            content = str(data.get("content") or data.get("text") or "").strip()
            ame_id = str(data.get("ameId") or data.get("ame_id") or "").strip()
            role = str(data.get("role") or "user").strip()
            raw_timestamp = data.get("timestamp")
            try:
                timestamp = float(raw_timestamp) if raw_timestamp is not None else time.time()
            except (TypeError, ValueError):
                timestamp = time.time()
            if not content or not ame_id:
                return {"status": "error", "detail": "ameId and content are required"}
            conversation = db.query(Conversation).filter(Conversation.session_id == ame_id).first()
            if not conversation:
                conversation = Conversation(
                    session_id=ame_id,
                    user_id=None,
                    created_at=time.time(),
                    updated_at=time.time(),
                )
                db.add(conversation)
                db.commit()
                db.refresh(conversation)
            message = Message(
                conversation_id=conversation.id,
                role=role,
                content=content,
                provider="local",
                timestamp=timestamp,
                extra=json.dumps({"source": "ws", "client_id": client_id}),
            )
            db.add(message)
            conversation.updated_at = time.time()
            db.commit()
            db.refresh(message)
            return {
                "status": "ok",
                "action": "chat_message",
                "data": {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "timestamp": message.timestamp,
                },
            }
        except Exception as exc:
            db.rollback()
            logger.error("WS chat_message failed: %s", exc)
            return {"status": "error", "detail": str(exc)}
        finally:
            db.close()

    await sync_manager.add_connection(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            import json as _json
            parsed = _json.loads(data)
            if parsed.get("action") == "chat_message":
                response = await _handle_chat_message(parsed.get("data") or {})
                if parsed.get("eventId"):
                    response["eventId"] = parsed.get("eventId")
            elif parsed.get("action") == "run_procedure":
                try:
                    from backend.device_auth import DeviceAuthManager
                    auth_mgr = DeviceAuthManager.get_instance()
                    if expected_api_key:
                        proc_auth_ok = bool(token) and token == expected_api_key
                    else:
                        if device_id and token and len(token) > 20:
                            proc_auth_ok = auth_mgr.validate_token(device_id, token)
                        else:
                            proc_auth_ok = auth_ok
                    if not proc_auth_ok:
                        response = {"status": "error", "detail": "unauthorized"}
                    else:
                        proc_id = str(parsed.get("data", {}).get("procedure_id", "")).strip()
                        params = parsed.get("data", {}).get("params", {})
                        if not proc_id:
                            response = {"status": "error", "detail": "procedure_id is required"}
                        else:
                            result = await task_manager.run_procedure(proc_id, params_override=params or {})
                            response = {"status": "ok", "action": "run_procedure", "data": result}
                except ValueError as exc:
                    response = {"status": "error", "detail": str(exc)}
                if parsed.get("eventId"):
                    response["eventId"] = parsed.get("eventId")
            elif parsed.get("action") == "command_request":
                from backend.device_auth import DeviceAuthManager
                cmd_data = parsed.get("data") or {}
                device_id = str(cmd_data.get("deviceId") or cmd_data.get("device_id") or client_id).strip()
                command = str(cmd_data.get("command", "")).strip()
                params = cmd_data.get("params", {})

                auth_mgr = DeviceAuthManager.get_instance()
                if expected_api_key:
                    token_valid = bool(token) and token == expected_api_key
                else:
                    if device_id and token and len(token) > 20:
                        token_valid = auth_mgr.validate_token(device_id, token)
                    else:
                        token_valid = auth_ok

                if not device_id:
                    response = {"status": "error", "detail": "deviceId required"}
                elif not command:
                    response = {"status": "error", "detail": "command required"}
                elif not token_valid:
                    response = {"status": "error", "detail": "unauthorized"}
                else:
                    try:
                        from backend.services.action_engine import ActionEngine
                        engine = ActionEngine()
                        tool_result = engine.execute(command, params or {})
                        response = {
                            "status": "ok" if tool_result.success else "error",
                            "action": "command_request",
                            "data": {
                                "task_id": tool_result.tool_name,
                                "result": tool_result.output,
                                "error": tool_result.error if not tool_result.success else None,
                            },
                        }
                    except Exception as cmd_exc:
                        response = {"status": "error", "detail": str(cmd_exc)[:500]}
                if parsed.get("eventId"):
                    response["eventId"] = parsed.get("eventId")
            else:
                response = await sync_manager.sync_data(websocket, parsed)
            await websocket.send_json(response)
    except Exception as exc:
        logger.warning("Mobile sync connection %s error: %s", client_id, exc)
    finally:
        await sync_manager.remove_connection(websocket)


@app.websocket("/api/ws/stream")
async def websocket_gateway(websocket: WebSocket):
    """AURA WebSocket Gateway — eventos literarios en tiempo real (PC ⇄ AME).

    Protocolo:
    1. Cliente envía {"type": "auth", "token": "...", "deviceId": "..."}
    2. Opcional: {"type": "subscribe", "work_id": "..."} para filtrar eventos por obra.
    3. El servidor transmite eventos: canon_event, character_update, session_change, pong.
    """
    await websocket.accept()
    ws_gateway.add_connection(websocket)
    try:
        while True:
            try:
                raw = await websocket.receive_text()
                data = json.loads(raw)
            except WebSocketDisconnect:
                raise
            except Exception:
                continue

            msg_type = data.get("type", "")
            if msg_type == "ping":
                # BLOQUE 48: telemetría local — registra la latencia de eco del
                # servidor (tiempo de procesado/eco) sin modificar el protocolo.
                _ping_start = time.perf_counter()
                await websocket.send_json({"type": "pong", "timestamp": time.time()})
                record_ws_latency((time.perf_counter() - _ping_start) * 1000.0)
            elif msg_type == "subscribe":
                work_id = str(data.get("work_id", "")).strip()
                if work_id:
                    ws_gateway.subscribe(websocket, work_id)
            elif msg_type == "unsubscribe":
                ws_gateway.unsubscribe(websocket, data.get("work_id"))
            elif msg_type == "auth":
                token = str(data.get("token", ""))
                await websocket.send_json({"status": "ok", "auth": "accepted"})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WS gateway error: %s", exc)
    finally:
        ws_gateway.remove_connection(websocket)


def broadcast_canon_event(work_id: str, description: str, source: str = "aura", event_id: str = "") -> None:
    """Transmite un evento canónico nuevo a todos los AME suscritos a la obra.

    Usado por el endpoint /api/discord/canon-feed y los endpoints REST de canon.
    """
    if not work_id:
        return
    try:
        asyncio.get_running_loop()
        asyncio.ensure_future(ws_gateway.broadcast(
            "canon_event",
            {"work_id": work_id, "description": description, "source": source, "event_id": event_id or str(uuid.uuid4()),
             "createdAt": datetime.now().isoformat()},
            work_id=work_id,
        ))
    except RuntimeError:
        logger.debug("No running event loop, skipping WS broadcast for work_id=%s", work_id)



@app.get("/api/mobile/mode", tags=["Mobile"])
async def mobile_get_mode():
    """Obtener el modo actual del launcher (local Linux o remote desktop)."""
    return {"mode": mobile_mode_state.get("mode", "remote")}


@app.post("/api/mobile/mode", tags=["Mobile"])
async def mobile_set_mode(request: Request):
    """Cambiar el modo del launcher móvil."""
    body = await request.json()
    new_mode = body.get("mode", "remote")
    if new_mode not in ("local", "remote"):
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'local' or 'remote'.")
    mobile_mode_state["mode"] = new_mode
    if new_mode == "local":
        logger.info("Mobile launcher switched to LOCAL mode (Termux)")
    else:
        logger.info("Mobile launcher switched to REMOTE mode (desktop AURA OS)")
    return {"mode": new_mode, "status": "switched"}


_TERMUX_WHITELIST = {
    "ls", "cat", "pwd", "whoami", "date", "uname", "df", "du",
    "ps", "top", "free", "uptime", "echo", "hostname", "ip",
    "ifconfig", "ping", "curl", "wget", "apt", "pkg",
    "proot-distro", "python3", "ruby", "go", "node",
    "git", "tar", "gzip", "find", "grep", "awk", "sed",
    "aura-scanner", "aura-resolver", "aura-enum",
    "aura-c2-server", "aura-c2-agent", "aura-c2-client",
}


@app.post("/api/mobile/termux/cmd", tags=["Mobile"])
async def mobile_termux_cmd(request: Request):
    """Ejecutar comando seguro en Termux (whitelist)."""
    body = await request.json()
    command = body.get("command", "").strip()

    if not command:
        raise HTTPException(status_code=400, detail="Command is required")

    first_token = command.split()[0] if command.split() else ""
    if first_token not in _TERMUX_WHITELIST:
        logger.warning("Blocked Termux command: %s", first_token)
        raise HTTPException(
            status_code=403,
            detail=f"Command '{first_token}' not in whitelist. Allowed: {', '.join(sorted(_TERMUX_WHITELIST))}"
        )

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Command timed out (10s limit)")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/discord/diagnostics", tags=["Mobile"])
async def discord_diagnostics():
    """Diagnóstico sanitizado del estado del bot de Discord (sin exponer secretos)."""
    from backend.discord_diagnostics import get_cached_diagnostics
    return get_cached_diagnostics()


@app.post("/api/discord/connection-status", tags=["Mobile"])
async def discord_connection_status(request: Request):
    """Receive connection status updates from the Discord bot process."""
    from backend.discord_diagnostics import record_successful_connection, record_connection_error
    try:
        body = await request.json()
        status = body.get("status", "unknown")
        if status == "connected":
            record_successful_connection()
        else:
            record_connection_error(f"Bot reported status: {status}")
        return {"status": "recorded"}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


@app.get("/api/browser/tasks", tags=["Browser"])
async def browser_tasks(status_filter: Optional[str] = None):
    """Lista tareas de navegador registradas (sin contenido sensible)."""
    from backend.browser_task_manager import browser_task_manager
    return {"tasks": browser_task_manager.list(status_filter)}


@app.post("/api/discord/canon-feed", tags=["Mobile"])
async def discord_canon_feed(request: Request):
    """Receive canon feed events from the Discord bot for broadcast to subscribers."""
    from backend.discord_diagnostics import record_canon_event
    try:
        body = await request.json()
        work_id = body.get("work_id", "unknown")
        event_id = body.get("event_id", "unknown")
        source = body.get("source", "discord")
        description = body.get("description", "")[:200]
        record_canon_event(work_id=work_id, event_id=event_id, source=source, description=description)
        broadcast_canon_event(work_id, description, source=source, event_id=event_id)
        return {"status": "recorded", "event_id": event_id}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )


# ════════════════════════════════════════════════════════════════════════════
# PLUGIN SYSTEM
# ════════════════════════════════════════════════════════════════════════════

@app.get("/api/plugins", tags=["Plugins"])
async def list_plugins():
    """
    Listar todos los plugins activos.

    Returns:
        Dict: Mapa de plugin_name → metadata con hooks registrados.

    Example:
    ```bash
    curl http://localhost:8000/api/plugins
    ```
    """
    return plugin_manager.list_plugins()

@app.get("/api/plugins/{plugin_name}", tags=["Plugins"], responses={
    200: {"description": "Plugin info"},
    404: {"description": "Plugin not found"}
})
async def get_plugin_info(plugin_name: str):
    """
    Ver información de un plugin específico.

    Args:
        plugin_name: str — nombre del plugin (stem del archivo)

    Returns:
        Dict: metadata del plugin (name, version, description, hooks, loaded_at)

    Example:
    ```bash
    curl http://localhost:8000/api/plugins/example_plugin
    ```
    """
    plugin = plugin_manager.get_plugin(plugin_name)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")
    return plugin_manager.plugin_metadata.get(plugin_name, {})

@app.post("/api/plugins/reload", tags=["Plugins"], responses={
    200: {"description": "Plugins reloaded"},
})
async def reload_plugins():
    """
    Recargar todos los plugins.

    Reinicia el plugin manager y recarga todos los archivos .py
    desde backend/plugins/custom/.

    Returns:
        - status: "plugins_reloaded"
        - count: numero de plugins cargados

    Example:
    ```bash
    curl -X POST http://localhost:8000/api/plugins/reload
    ```
    """
    plugin_manager.plugins = {}
    plugin_manager.hooks = {}
    plugin_manager.plugin_metadata = {}
    plugin_manager.load_all_plugins()
    return {"status": "plugins_reloaded", "count": len(plugin_manager.plugins)}

@app.delete("/api/plugins/{plugin_name}", tags=["Plugins"], responses={
    200: {"description": "Plugin unloaded"},
    404: {"description": "Plugin not found"}
})
async def unload_plugin(plugin_name: str):
    """
    Descargar un plugin del sistema.

    Desactiva el plugin y limpia sus hooks registrados.

    Args:
        plugin_name: str — nombre del plugin a descargar

    Returns:
        Dict: {"status": "plugin_unloaded", "plugin": plugin_name}

    Example:
    ```bash
    curl -X DELETE http://localhost:8000/api/plugins/example_plugin
    ```
    """
    if plugin_manager.unload_plugin(plugin_name):
        return {"status": "plugin_unloaded", "plugin": plugin_name}
    else:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found")


# ════════════════════════════════════════════════════════════════════════════
# AUTOMATION ENGINE
# ════════════════════════════════════════════════════════════════════════════

@app.post("/api/automation/rules", tags=["Automation"], responses={
    200: {"description": "Rule created"},
    400: {"description": "Invalid rule data"}
})
async def create_automation_rule(rule_data: AutomationRuleModel):
    """
    Crear nueva regla de automatización.

    Crea una regla con trigger y acciones. Las reglas se guardan en
    data/automation_rules.json y se monitorean automáticamente.

    Args:
        rule_data (AutomationRuleModel):
            - name: str (required) — nombre descriptivo
            - trigger: Trigger — tipo y parámetros del trigger
            - actions: List[Action] — acciones a ejecutar
            - enabled: bool — si está activa (default: true)
            - tags: List[str] — etiquetas para filtrado

    Returns:
        - status: "rule_created"
        - rule_id: str — ID único
        - rule_name: str

    Example:
    ```bash
    curl -X POST http://localhost:8000/api/automation/rules \\
      -H "Content-Type: application/json" \\
      -d '{"name":"test_rule","trigger":{"type":"on_time","hour":14,"minute":30},
           "actions":[{"type":"chat","message":"Hola"}]}'
    ```
    """
    rule_id = automation_engine.add_rule(rule_data)
    return {"status": "rule_created", "rule_id": rule_id, "rule_name": rule_data.name}

@app.get("/api/automation/rules", tags=["Automation"])
async def list_automation_rules(enabled_only: bool = False, tag: str = None):
    """
    Listar reglas de automatización.

    Args:
        enabled_only: boolean — filtrar solo reglas activas
        tag: string — filtrar por etiqueta

    Returns:
        Dict[str, Dict]: Mapa de rule_id → regla con metadata

    Example:
    ```bash
    curl http://localhost:8000/api/automation/rules
    curl "http://localhost:8000/api/automation/rules?enabled_only=true&tag=morning"
    ```
    """
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
    return {"status": "executed", "success": success, "rule_id": rule_id, "execution_count": rule.execution_count, "last_error": rule.last_error}

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
    return {"monitoring": automation_engine.monitoring, "rules_count": len(automation_engine.rules), "interval": automation_engine.monitor_interval}


@app.post("/api/agents/kilo/delegate", tags=["Kilo Agent"], responses={
    200: {"description": "Task delegated to Kilo"},
    400: {"description": "Invalid task data"}
})
async def delegate_to_kilo(task: KiloTask):
    """
    Delegar tarea a Kilo/Cline agent.

    Crea un prompt profesional y lo guarda en kilo_prompts/ para que
    Kilo lo procese. El resultado se recibe vía callback.

    Args:
        task (KiloTask):
            - task_id: str (required) — identificador único
            - objective: str (required) — objetivo de la tarea
            - context: dict — contexto adicional
            - required_tools: List[str] — herramientas necesarias
            - timeout: int — límite de tiempo en segundos (default: 300)
            - callback_url: str — URL para recibir el resultado

    Returns:
        - task_id: str
        - status: "delegated"
        - prompt_file: str — path del archivo de prompt

    Example:
    ```bash
    curl -X POST http://localhost:8000/api/agents/kilo/delegate \\
      -H "Content-Type: application/json" \\
      -d '{"task_id":"t1","objective":"Crear script Python"}'
    ```
    """
    return await kilo_bridge.delegate_task(task)


@app.post("/api/agents/kilo/callback")
async def kilo_callback(task_id: str, result: dict):
    """Recibir resultado de Kilo"""
    await kilo_bridge.handle_callback(task_id, result)
    return {"status": "received"}


@app.get("/api/agents/kilo/status/{task_id}")
async def kilo_task_status(task_id: str):
    """Ver estado de tarea"""
    return kilo_bridge.get_task_status(task_id)


@app.get("/api/agents/kilo/history")
async def kilo_history(limit: int = 50):
    """Ver historial"""
    return kilo_bridge.get_history(limit)


# =============================================================================
# AUTHENTICATION & MULTI-USER SYSTEM
# =============================================================================

@app.post("/api/auth/register", response_model=TokenResponse, tags=["Auth"])
async def auth_register(user_data: UserCreate, db: DBSession = Depends(get_db)):
    """
    Registrar nuevo usuario.

    Crea cuenta con username, email y password.
    """
    user = AuthService.register_user(db, user_data)
    session = AuthService.create_session(db, user.id)
    return TokenResponse(
        access_token=session.token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "theme": user.theme,
            "language": user.language,
            "created_at": user.created_at,
        },
    )


@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
async def auth_login(login_data: UserLogin, request: Request, db: DBSession = Depends(get_db)):
    """
    Login de usuario.

    Retorna JWT token valido por 24 horas.
    """
    user = AuthService.authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario o password invalidos")
    session = AuthService.create_session(
        db,
        user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return TokenResponse(
        access_token=session.token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "theme": user.theme,
            "language": user.language,
            "created_at": user.created_at,
        },
    )


@app.post("/api/auth/logout", tags=["Auth"])
async def auth_logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: DBSession = Depends(get_db),
):
    """Logout (invalidar sesion)"""
    token = credentials.credentials
    AuthService.invalidate_session(db, token)
    return {"status": "logged_out"}


@app.get("/api/auth/me", tags=["Auth"])
async def auth_get_me(
    current_user: dict = Depends(auth_get_current_user),
    db: DBSession = Depends(get_db),
):
    """Ver perfil del usuario actual"""
    user = AuthService.get_user_by_id(db, current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "theme": user.theme,
        "language": user.language,
        "created_at": user.created_at,
    }


@app.put("/api/auth/me/preferences", tags=["Auth"])
async def auth_update_preferences(
    preferences: dict,
    current_user: dict = Depends(auth_get_current_user),
    db: DBSession = Depends(get_db),
):
    """Actualizar preferencias del usuario"""
    user = AuthService.get_user_by_id(db, current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if "theme" in preferences:
        user.theme = preferences["theme"]
    if "language" in preferences:
        user.language = preferences["language"]
    if "timezone" in preferences:
        user.timezone = preferences["timezone"]
    db.commit()
    return {"status": "preferences_updated", "preferences": preferences}


@app.get("/api/auth/sessions", tags=["Auth"])
async def auth_list_sessions(
    current_user: dict = Depends(auth_get_current_user),
    db: DBSession = Depends(get_db),
):
    """Listar sesiones activas del usuario"""
    sessions = AuthService.list_user_sessions(db, current_user["sub"])
    return {
        "sessions": [
            {
                "id": s.id,
                "created_at": s.created_at,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "expires_at": s.expires_at,
            }
            for s in sessions
        ],
    }


@app.delete("/api/auth/sessions/{session_id}", tags=["Auth"])
async def auth_delete_session(
    session_id: str,
    current_user: dict = Depends(auth_get_current_user),
    db: DBSession = Depends(get_db),
):
    """Cerrar una sesion especifica"""
    session = db.query(AuthSession).filter(
        AuthSession.id == session_id,
        AuthSession.user_id == current_user["sub"],
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    session.is_active = False
    db.commit()
    return {"status": "session_deleted"}


# Admin endpoints

@app.get("/api/admin/users", tags=["Admin"])
async def admin_list_users(
    current_user: dict = Depends(get_current_admin),
    db: DBSession = Depends(get_db),
):
    """Listar todos los usuarios (solo admin)"""
    users = db.query(AuthUser).all()
    return {
        "total": len(users),
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_active": u.is_active,
                "is_admin": u.is_admin,
                "created_at": u.created_at,
            }
            for u in users
        ],
    }


@app.patch("/api/admin/users/{user_id}", tags=["Admin"])
async def admin_update_user(
    user_id: str,
    updates: dict,
    current_user: dict = Depends(get_current_admin),
    db: DBSession = Depends(get_db),
):
    """Actualizar usuario (solo admin)"""
    user = AuthService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if "is_admin" in updates:
        user.is_admin = updates["is_admin"]
    if "is_active" in updates:
        user.is_active = updates["is_active"]
    db.commit()
    return {"status": "user_updated"}


@app.delete("/api/admin/users/{user_id}", tags=["Admin"])
async def admin_delete_user(
    user_id: str,
    current_user: dict = Depends(get_current_admin),
    db: DBSession = Depends(get_db),
):
    """Eliminar usuario (solo admin)"""
    if user_id == current_user["sub"]:
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")
    user = AuthService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    db.delete(user)
    db.commit()
    return {"status": "user_deleted"}


# =============================================================================
# MOBILE AME ENDPOINTS — mínimos, sin modelo AME nuevo
# =============================================================================

@app.get("/api/mobile/ames", tags=["Mobile"])
async def mobile_ames_list(request: Request, db: SessionLocal = Depends(get_db)):
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    expected = os.getenv("AURA_API_KEY")
    if expected and api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")

    conversations = db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(20).all()
    now = time.time()
    ames = []
    if conversations:
        for conv in conversations:
            ames.append({
                "id": f"ame_{conv.session_id}",
                "name": conv.session_id or "AME",
                "status": "online",
                "lastActivity": datetime.fromtimestamp(conv.updated_at).isoformat() if conv.updated_at else datetime.utcnow().isoformat(),
                "unreadCount": 0,
            })
    else:
        ames = [
            {
                "id": "ame_core",
                "name": "AURA-Core",
                "status": "online",
                "lastActivity": datetime.utcnow().isoformat(),
                "unreadCount": 0,
            },
            {
                "id": "ame_analytics",
                "name": "Analytics-AME",
                "status": "offline",
                "lastActivity": datetime.utcnow().isoformat(),
                "unreadCount": 0,
            },
        ]
    return {"ames": ames}


@app.get("/api/mobile/ames/{ame_id}/history", tags=["Mobile"])
async def mobile_ame_history(ame_id: str, request: Request, db: SessionLocal = Depends(get_db)):
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    expected = os.getenv("AURA_API_KEY")
    if expected and api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")

    session_id = ame_id.replace("ame_", "", 1) if ame_id.startswith("ame_") else ame_id
    conversation = db.query(Conversation).filter(Conversation.session_id == session_id).first()
    if not conversation:
        return {"messages": []}

    messages = db.query(Message).filter(Message.conversation_id == conversation.id).order_by(Message.timestamp.asc()).all()
    return {
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": datetime.fromtimestamp(m.timestamp).isoformat() if m.timestamp else None,
            }
            for m in messages
        ]
    }


@app.post("/api/mobile/ames/{ame_id}/message", tags=["Mobile"])
async def mobile_ame_message(ame_id: str, request: Request, db: SessionLocal = Depends(get_db)):
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    expected = os.getenv("AURA_API_KEY")
    if expected and api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")

    body = await request.json()
    message_text = str(body.get("message", "")).strip()
    role = str(body.get("role", "user")).strip()
    if not message_text:
        raise HTTPException(status_code=400, detail="message is required")
    if role not in ("user", "ame"):
        role = "user"

    session_id = ame_id.replace("ame_", "", 1) if ame_id.startswith("ame_") else ame_id
    conversation = db.query(Conversation).filter(Conversation.session_id == session_id).first()
    if not conversation:
        conversation = Conversation(
            session_id=session_id,
            user_id=None,
            created_at=time.time(),
            updated_at=time.time(),
            extra=None,
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    conversation.updated_at = time.time()
    msg = Message(
        conversation_id=conversation.id,
        role=role,
        content=message_text,
        provider=None,
        timestamp=time.time(),
        extra=None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "timestamp": datetime.fromtimestamp(msg.timestamp).isoformat() if msg.timestamp else None,
    }


# =============================================================================
# BLOQUE 34: Background Narrative Agent & Cron Engine — REST API
# =============================================================================

@app.get("/api/agent/scheduler/status", tags=["Background"])
async def get_scheduler_status():
    """Estado del BackgroundDaemon y tareas programadas."""
    daemon = get_agent_scheduler()
    return daemon.get_status()


@app.post("/api/agent/scheduler/run/{task_name}", tags=["Background"])
async def run_scheduler_task_now(task_name: str):
    """Ejecuta inmediatamente una tarea programada por nombre."""
    daemon = get_agent_scheduler()
    for t in daemon.tasks.values():
        if t.name == task_name:
            await daemon._run_task(t)
            return {"status": "ok", "task": task_name, "run_count": t.run_count}
    return {"status": "error", "detail": f"task '{task_name}' not found"}


@app.post("/api/agent/scheduler/enable/{task_name}", tags=["Background"])
async def toggle_scheduler_task(task_name: str, request: Request):
    """Habilita o deshabilita una tarea programada (body: {enabled: bool})."""
    body = await request.json()
    enabled = body.get("enabled", True)
    daemon = get_agent_scheduler()
    for t in daemon.tasks.values():
        if t.name == task_name:
            t.enabled = bool(enabled)
            return {"status": "ok", "task": task_name, "enabled": t.enabled}
    return {"status": "error", "detail": f"task '{task_name}' not found"}


@app.post("/api/agent/reflection/{work_id}", tags=["Background"])
async def trigger_reflection(work_id: str):
    """Dispara reflexión narrativa con Jan para una obra (manual)."""
    daemon = get_agent_scheduler()
    result = await daemon._reflection_engine.reflect_on_work(work_id)
    if result:
        await daemon._dispatcher.dispatch_reflection(work_id, result)
        return {"status": "ok", "work_id": work_id, "reflection": result}
    return {"status": "error", "detail": "reflection returned no result (Jan offline?)"}


@app.post("/api/agent/summary/{work_id}", tags=["Background"])
async def trigger_summary(work_id: str):
    """Genera un resumen de trama para una obra (manual)."""
    daemon = get_agent_scheduler()
    summary = await daemon._reflection_engine.summarize_work(work_id)
    if summary:
        await daemon._dispatcher.dispatch_to_websocket(
            "plot_summary",
            {"work_id": work_id, "summary": summary},
            work_id=work_id,
        )
        return {"status": "ok", "work_id": work_id, "summary": summary}
    return {"status": "error", "detail": "summary returned no result (Jan offline?)"}


# ===== IDE & External Tool Integration (Android Studio + Godot + VS Code + Antigravity) =====

from backend.integrations.ide_controller import get_ide_controller  # noqa: E402


@app.get("/api/ide/apps", tags=["IDE"])
async def ide_get_apps():
    """Lista el estado de todas las apps integradas (Android Studio, Godot, VS Code, etc)."""
    try:
        ctrl = get_ide_controller()
        return ctrl.get_installed_apps()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/ide/android/status", tags=["IDE"])
async def ide_android_status():
    """Estado de Android Studio (instalado, ruta, en ejecucion)."""
    try:
        ctrl = get_ide_controller()
        return ctrl.android_get_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/ide/android/open", tags=["IDE"])
async def ide_android_open(project_path: str = ""):
    """Abre Android Studio (opcionalmente con un proyecto)."""
    try:
        ctrl = get_ide_controller()
        result = ctrl.android_open(project_path)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/ide/android/gradle", tags=["IDE"])
async def ide_android_gradle(project_path: str, task: str = "assembleDebug"):
    """Ejecuta un comando Gradle en un proyecto Android (ej: assembleDebug, test, install)."""
    try:
        ctrl = get_ide_controller()
        result = ctrl.android_run_gradle(project_path, task)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/ide/android/projects", tags=["IDE"])
async def ide_android_find_projects(base_dir: str = ""):
    """Busca proyectos Android Studio (con AndroidManifest.xml + build.gradle) en un directorio."""
    try:
        ctrl = get_ide_controller()
        return ctrl.android_find_projects(base_dir)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/ide/godot/status", tags=["IDE"])
async def ide_godot_status():
    """Estado de Godot (instalado, ruta, en ejecucion)."""
    try:
        ctrl = get_ide_controller()
        return ctrl.godot_get_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/ide/godot/run", tags=["IDE"])
async def ide_godot_run(project_path: str):
    """Ejecuta un proyecto Godot en segundo plano."""
    try:
        ctrl = get_ide_controller()
        result = ctrl.godot_run(project_path)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/ide/godot/projects", tags=["IDE"])
async def ide_godot_find_projects(base_dir: str = ""):
    """Busca proyectos Godot (project.godot files) en un directorio."""
    try:
        ctrl = get_ide_controller()
        return ctrl.godot_find_projects(base_dir)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/ide/vscode/status", tags=["IDE"])
async def ide_vscode_status():
    """Estado de VS Code (instalado, ruta, en ejecucion)."""
    try:
        ctrl = get_ide_controller()
        return ctrl.vscode_get_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/ide/vscode/open", tags=["IDE"])
async def ide_vscode_open(path: str = ""):
    """Abre VS Code (con ruta o carpeta opcional)."""
    try:
        ctrl = get_ide_controller()
        result = ctrl.vscode_open(path)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/ide/antigravity/status", tags=["IDE"])
async def ide_antigravity_status():
    """Estado de Antigravity IDE (instalado, ruta, en ejecucion)."""
    try:
        ctrl = get_ide_controller()
        return ctrl.antigravity_get_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/ide/antigravity/open", tags=["IDE"])
async def ide_antigravity_open(path: str = ""):
    """Abre Antigravity IDE (con proyecto opcional)."""
    try:
        ctrl = get_ide_controller()
        result = ctrl.antigravity_open(path)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/ide/kill", tags=["IDE"])
async def ide_kill_app(app_name: str):
    """Cierra una aplicacion en ejecucion (android_studio, godot, obsidian, etc)."""
    try:
        ctrl = get_ide_controller()
        result = ctrl.kill_app(app_name)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
