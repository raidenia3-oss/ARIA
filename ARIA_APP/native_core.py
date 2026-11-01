# -*- coding: utf-8 -*-
"""ARIA OS Native Core — todo-en-uno, sin HTTP, sin servidores, sin puertos.

Arquitectura de proceso único:
  UI (PyQt5)  <->  Logic Engine (mismo proceso, llamada directa)
                      <->  AI Provider (Ollama localhost:11434 o local fallback)

Nunca se abre un puerto TCP. No hay FastAPI, no hay uvicorn, no hay navegador.
La app es una ventana nativa de escritorio con orb, chat, skills y centro de control.
"""
from __future__ import annotations

import json
import os
import sys
import time
import threading
import logging
import queue
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QTextEdit, QLineEdit, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QFrame, QSizePolicy, QScrollArea, QShortcut,
    QGraphicsDropShadowEffect, QInputDialog)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt5.QtGui import QPainter, QColor, QFont, QPen, QBrush, QRadialGradient

ARIA_APP = Path(__file__).resolve().parent
PROJECT_ROOT = ARIA_APP.parent
load_dotenv(str(ARIA_APP / ".env"))

# ─── Nuevos módulos de IA, Memoria, RAG y Entornos ──────────────────────────
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(ARIA_APP))
from backend.ai.models import AIModelManager, ModelType
from backend.ai.training_engine import AITrainingEngine
from backend.ai.model_improver import ModelImprover
from backend.memory.short_term import ShortTermMemory
from backend.memory.long_term import LongTermMemory
from backend.memory.vector_store import VectorMemoryStore
from backend.memory.consolidation import MemoryConsolidator
from backend.memory.mnemosyne import MnemosyneMemory
from backend.memory.hindsight import HindsightMemory
from backend.memory.obsidian_wiki import ObsidianWiki
from backend.process_guard import get_guard
from backend.rag.engine import EnhancedRAG
from backend.environments.base import BaseEnvironment
from backend.environments.research import ResearchEnvironment
from backend.environments.brain import BrainEnvironment
from backend.environments.optimization import OptimizationEnvironment
from backend.environments.autonomous import AutonomousEnvironment
from backend.environments.innovation import InnovationEnvironment
from backend.skills.discord import run as discord_run
from backend.skills.github import run as github_run
from backend.skills.system.power import run as power_run
from backend.skills.system.wol import run as wol_run
from backend.skills.system.power_monitor import run as power_monitor_run
from backend.skills.web import run as web_run
from backend.skills.files import run as files_run
from backend.skills.android import run as android_run
from backend.skills.media_extractor import run as media_extract_run
from backend.skills.desktop import run as desktop_run
from backend.sandbox.manager import SandboxManager
from backend.sandbox.types import SandboxConfig

LOG_DIR = ARIA_APP / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "aria_native.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("ARIA")

# ─── AI Provider (Ollama local o fallback) ──────────────────────────────────


class NativeAIProvider:
    """Proveedor de IA para ARIA OS nativo.

    Prioridad: Ollama (localhost:11434) -> local rule-based fallback.
    Nunca usa APIs cloud salvo que se configure explícitamente.
    """

    def __init__(self) -> None:
        self.base_url = os.getenv("ARIA_OLLAMA_URL", "http://localhost:11434")
        self.model = os.getenv("ARIA_OLLAMA_MODEL", "granite3.2-vision:2b")
        self.system_prompt = os.getenv(
            "ARIA_SYSTEM_PROMPT",
            "Eres ARIA, un asistente personal avanzado estilo Jarvis/Ultron. Responde en español.",
        )
        self._session = None
        self._available = None
        self._check_ollama()

    def _check_ollama(self) -> None:
        import urllib.request
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                if r.status == 200:
                    self._available = True
                    logger.info(f"Ollama disponible en {self.base_url}")
                    return
        except Exception:
            pass
        self._available = False
        logger.warning("Ollama no disponible; usando modo local")

    def is_available(self) -> bool:
        return bool(self._available)

    def chat(self, message: str, history: Optional[List[List[str]]] = None,
             system_prompt: Optional[str] = None, temperature: float = 0.7,
             max_tokens: int = 1024) -> Dict[str, Any]:
        """Devuelve {"response": str, "provider": str, "latency": float}."""
        start = time.time()
        sp = system_prompt or self.system_prompt

        if self._available:
            try:
                import urllib.request
                msgs = [{"role": "system", "content": sp}]
                if history:
                    for u, a in history[-10:]:
                        msgs.append({"role": "user", "content": u})
                        msgs.append({"role": "assistant", "content": a})
                msgs.append({"role": "user", "content": message})
                body = json.dumps({
                    "model": self.model,
                    "messages": msgs,
                    "stream": False,
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }).encode()
                req = urllib.request.Request(
                    f"{self.base_url}/api/chat",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = json.loads(r.read())
                text = ((data.get("message") or {}).get("content") or "").strip()
                if text:
                    return {"response": text, "provider": "ollama",
                            "latency": round(time.time() - start, 2)}
            except Exception as exc:
                logger.error(f"Ollama chat error: {exc}")

        # Fallback local
        text = self._local_response(message)
        return {"response": text, "provider": "local", "latency": round(time.time() - start, 2)}

    def _local_response(self, message: str) -> str:
        lower = message.lower()
        if any(g in lower for g in ["hola", "buenas", "hello", "hi"]):
            return "Hola, soy ARIA. Tu asistente nativo, sin servidor, sin puertos. ¿En qué te ayudo?"
        if any(g in lower for g in ["como estas", "cómo estás", "que tal", "qué tal"]):
            return "Estoy operativa. Sistema nativo activo, escuchando."
        if "estado" in lower or "status" in lower:
            return "ARIA OS nativo: UI activa, motor de lógica en proceso, IA local (Ollama) " + ("disponible" if self._available else "no disponible, modo local")
        if "puertos" in lower or "servidor" in lower or "http" in lower:
            return "ARIA no abre puertos ni corre servidores HTTP. Todo corre en proceso local, offline-capable."
        return f"Recibido: '{message}'. Modo local activo. Configura Ollama para respuestas con IA."


# ─── Logic Engine (in-proceso, llamada directa) ─────────────────────────────


class NativeLogicEngine:
    """Motor de lógica de ARIA. Se llama directamente desde la UI (mismo proceso)."""

    def __init__(self, ai: NativeAIProvider) -> None:
        self.ai = ai
        self.start_time = time.time()
        self._skills: Dict[str, Any] = {}
        self._kg = None
        self._load_builtin_skills()
        self.continuous = ContinuousEngine(self)
        self._kg = self.continuous._kg

        # ─── Nuevos componentes de IA ────────────────────────────────────────
        self.ai_model_manager = AIModelManager()
        self.ai_training_engine = AITrainingEngine()
        self.ai_model_improver = ModelImprover()

        # ─── Sistema de memoria ─────────────────────────────────────────────
        self.stm = ShortTermMemory(max_entries=100)
        self.ltm = LongTermMemory(data_dir=str(ARIA_APP / "data" / "memory" / "long_term"))
        self.vs = VectorMemoryStore(data_dir=str(ARIA_APP / "data" / "memory" / "vector"))
        self.memory_consolidator = MemoryConsolidator(self.stm, self.ltm, self.vs)

        # ─── Tres capas de memoria (Mnemosyne / Hindsight / Obsidian Wiki) ───
        # Mnemosyne: buffer operativo de sesión, zero-dependency.
        # Hindsight: reflexión con LLM sobre el pasado (preferencias, patrones).
        # Obsidian Wiki: conocimiento permanente en Markdown.
        self.mnemosyne = MnemosyneMemory(
            data_dir=str(ARIA_APP / "data" / "memory" / "mnemosyne"))
        self.hindsight = HindsightMemory(
            data_dir=str(ARIA_APP / "data" / "memory" / "hindsight"))
        self.wiki = ObsidianWiki(
            data_dir=str(ARIA_APP / "data" / "memory" / "obsidian_wiki"))
        self.hindsight.set_llm_provider(self._llm_for_hindsight)

        # ─── Guard de procesos (nunca tocar sesiones del usuario) ───────────
        self.process_guard = get_guard()

        # ─── Motor RAG ──────────────────────────────────────────────────────
        self.rag = EnhancedRAG(
            data_dir=str(ARIA_APP / "data" / "rag"),
            model_manager=self.ai_model_manager,
        )

        # ─── Entornos ───────────────────────────────────────────────────────
        self.environments: Dict[str, BaseEnvironment] = {
            "investigacion": ResearchEnvironment(),
            "cerebro_global": BrainEnvironment(),
            "optimizacion": OptimizationEnvironment(),
            "agentes_autonomos": AutonomousEnvironment(),
            "innovacion": InnovationEnvironment(),
        }

        logger.info("NativeLogicEngine initialized con IA, memoria, RAG y entornos")

        # ─── Super Sandbox (ejecución aislada, sin HTTP, sin puertos) ─────────
        self.sandbox = SandboxManager(self, str(PROJECT_ROOT / "data" / "sandbox"))

        # ─── Integraciones externas: Discord y GitHub ─────────────────────────
        self.discord_token = os.environ.get("DISCORD_BOT_TOKEN", "")
        self.github_client = None  # se crea bajo demanda en github_run

    def _llm_for_hindsight(self, prompt: str) -> str:
        """Adaptador del proveedor de IA de ARIA para el motor Hindsight.

        Hindsight espera un callable que devuelva texto plano. Si Ollama no
        esta disponible devuelve cadena vacia y Hindsight cae a su resumen
        basico sin LLM.
        """
        try:
            if not self.ai.is_available():
                return ""
            result = self.ai.chat(
                message=prompt,
                system_prompt=(
                    "Eres el motor de reflexion de ARIA OS. Analiza la conversacion "
                    "y responde SOLO con JSON valido con esta forma: "
                    "{summary: texto, preferences: [texto, ...], patterns: [texto, ...]}. "
                    "Sin texto antes ni despues del JSON."
                ),
                temperature=0.2,
                max_tokens=900,
            )
            return str((result or {}).get("response", ""))
        except Exception as exc:
            logger.warning(f"Hindsight: proveedor de IA no disponible: {exc}")
            return ""

    def _load_builtin_skills(self) -> None:
        self._skills = {
            "status": {"desc": "Estado del sistema ARIA", "category": "system"},
            "skills": {"desc": "Listar habilidades disponibles", "category": "system"},
            "ping": {"desc": "Prueba de conectividad interna", "category": "system"},
            "time": {"desc": "Hora y fecha actual", "category": "system"},
            "drive": {"desc": "Procesar medios de Google Drive (autónomo)", "category": "vision"},
            "net_scan": {"desc": "Escanear hosts activos en la red (nmap)", "category": "red"},
            "wifi_scan": {"desc": "Escanear redes WiFi cercanas (nmcli/iwlist)", "category": "red"},
            "mac_spoof": {"desc": "Cambiar MAC de interfaz (macchanger)", "category": "red"},
            "tor_status": {"desc": "Estado de anonimato Tor", "category": "red"},
            "whois_lookup": {"desc": "Consultar registros whois de dominio", "category": "red"},
            "packet_capture": {"desc": "Capturar paquetes de red (tcpdump)", "category": "red"},
            "kali_care": {"desc": "Mantenimiento y diagnóstico de seguridad Kali (estilo KaliCare)", "category": "seguridad"},
            "nmap_full": {"desc": "Escaneo completo de puertos y servicios (nmap -sS -sV)", "category": "red"},
            "metasploit": {"desc": "Reconocimiento y generación de payload (msfconsole/msfvenom, solo lectura)", "category": "seguridad"},
            "drive_analyze": {"desc": "Analiza Drive y archivos locales, extrae detalles clave y patrones", "category": "drive"},
            "creative_ideas": {"desc": "Genera ideas creativas basadas en conocimiento acumulado", "category": "creatividad"},
            "auto_improve": {"desc": "Auto-evaluación y propuestas de mejora del sistema", "category": "auto-mejora"},
            "autonomo_start": {"desc": "Inicia el motor de operación continua (auto-mejora en bucle)", "category": "autonomo"},
            "autonomo_stop": {"desc": "Detiene el motor de operación continua", "category": "autonomo"},
            "instagram_video": {"desc": "Ver un video/reel de cualquier plataforma SIN descargarlo (metadatos, miniatura con visión, clasificación JEV)", "category": "social"},
            "instagram_re": {"desc": "Analiza Instagram.com con REA (ingeniería inversa de sitio web: estructura, scripts, red)", "category": "social"},
            "media_related": {"desc": "Extrae contenido relacionado de la plataforma (reels relacionados, colaboradores, lugares, productos, sonidos, listas de reproducción)", "category": "social"},
            "rag_retrieve": {"desc": "Recupera contexto relevante usando motor RAG (búsqueda semántica + vectorial)", "category": "ia"},
            "rag_add": {"desc": "Agrega texto/conversación al sistema RAG para indexación y búsqueda futura", "category": "ia"},
            "memory_add": {"desc": "Agrega entrada a memoria corto/largo plazo", "category": "memoria"},
            "memory_search": {"desc": "Busca en memoria corto y largo plazo", "category": "memoria"},
            "memory_consolidate": {"desc": "Consolida memoria: promueve entradas importantes de corto a largo plazo", "category": "memoria"},
            "memory_stats": {"desc": "Estadísticas del sistema de memoria", "category": "memoria"},
            "memory_layers": {"desc": "Estado de las 3 capas de memoria (Mnemosyne, Hindsight, Obsidian Wiki)", "category": "memoria"},
            "mnemosyne_add": {"desc": "Guarda una entrada en Mnemosyne (buffer de sesion, zero-dependency)", "category": "memoria"},
            "mnemosyne_search": {"desc": "Busca en Mnemosyne por palabras clave", "category": "memoria"},
            "hindsight_reflect": {"desc": "Reflexiona con LLM sobre una conversacion y extrae preferencias y patrones", "category": "memoria"},
            "hindsight_insights": {"desc": "Lista los insights aprendidos por Hindsight", "category": "memoria"},
            "hindsight_context": {"desc": "Contexto de Hindsight relevante para una consulta", "category": "memoria"},
            "wiki_write": {"desc": "Escribe una nota Markdown permanente en el wiki (Obsidian)", "category": "memoria"},
            "wiki_read": {"desc": "Lee una nota del wiki por titulo o id", "category": "memoria"},
            "wiki_search": {"desc": "Busca notas en el wiki por contenido o tag", "category": "memoria"},
            "process_guard_status": {"desc": "Politica de terminacion de procesos y procesos protegidos (nunca toca los del usuario)", "category": "system"},
            "process_list": {"desc": "Lista procesos visibles con su estado frente al guard (sin terminar nada)", "category": "system"},
            "process_terminate": {"desc": "Termina un PID especifico SOLO si lo permite el guard (nunca por nombre)", "category": "system"},
            "ai_models": {"desc": "Lista modelos de IA disponibles y sus capacidades", "category": "ia"},
            "ai_train": {"desc": "Inicia entrenamiento de IA asistente personal (fine-tuning, LoRA, etc.)", "category": "ia"},
            "ai_train_status": {"desc": "Consulta el estado de un trabajo de entrenamiento", "category": "ia"},
            "ai_improve": {"desc": "Mejora reconocimiento de contenido (video, foto, cualquier formato)", "category": "ia"},
            "env_start": {"desc": "Inicia un entorno especializado (investigacion, cerebro_global, optimizacion, agentes_autonomos, innovacion)", "category": "entorno"},
            "env_stop": {"desc": "Detiene un entorno especializado", "category": "entorno"},
            "env_process": {"desc": "Procesa una tarea dentro de un entorno", "category": "entorno"},
            "env_status": {"desc": "Estado de todos los entornos", "category": "entorno"},
            "env_list": {"desc": "Lista entornos disponibles", "category": "entorno"},
            "sandbox_exec": {"desc": "Ejecuta código Python dentro del super sandbox aislado (sin red, solo directorio temporal)", "category": "sandbox"},
            "sandbox_skill": {"desc": "Ejecuta una skill de ARIA dentro del super sandbox aislado", "category": "sandbox"},
            "sandbox_status": {"desc": "Consulta el estado de un sandbox por su ID", "category": "sandbox"},
            "sandbox_stop": {"desc": "Detiene un sandbox en ejecución por su ID", "category": "sandbox"},
            "sandbox_list": {"desc": "Lista todos los sandboxes activos (código y skills)", "category": "sandbox"},
            "discord_connect": {"desc": "Conecta el bot de Discord (token desde DISCORD_BOT_TOKEN)", "category": "discord"},
            "discord_disconnect": {"desc": "Desconecta el bot de Discord", "category": "discord"},
            "discord_status": {"desc": "Estado de conexión del bot de Discord", "category": "discord"},
            "discord_guilds": {"desc": "Lista servidores de Discord", "category": "discord"},
            "discord_channels": {"desc": "Lista canales de un servidor de Discord", "category": "discord"},
            "discord_send": {"desc": "Envía un mensaje a un canal de Discord", "category": "discord"},
            "discord_read": {"desc": "Lee mensajes recientes de un canal de Discord", "category": "discord"},
            "github_list_repos": {"desc": "Lista tus repositorios de GitHub", "category": "github"},
            "github_search_repos": {"desc": "Busca repositorios en GitHub", "category": "github"},
            "github_get_repo": {"desc": "Obtiene detalles de un repositorio de GitHub", "category": "github"},
            "github_file_content": {"desc": "Obtiene el contenido de un archivo de un repo de GitHub", "category": "github"},
            "github_list_dir": {"desc": "Lista el contenido de un directorio de un repo de GitHub", "category": "github"},
            "github_issues": {"desc": "Lista issues de un repositorio de GitHub", "category": "github"},
            "github_auth": {"desc": "Verifica autenticación de GitHub", "category": "github"},
            "power_status": {"desc": "Detecta estado de energia (AC/bateria) de esta PC", "category": "system"},
            "power_wake_on_ac_info": {"desc": "Info para configurar encendido al conectar cargador (BIOS/UEFI)", "category": "system"},
            "power_monitor_start": {"desc": "Inicia monitoreo continuo de energia; al detectar cargador conectado envia WoL a targets", "category": "system"},
            "power_monitor_stop": {"desc": "Detiene el monitoreo continuo de energia", "category": "system"},
            "power_monitor_status": {"desc": "Estado del monitor de energia y eventos recientes", "category": "system"},
            "wol_add_target": {"desc": "Agrega una MAC a la lista de equipos que se encienden al conectar el cargador", "category": "system"},
            "wol_remove_target": {"desc": "Remueve una MAC de la lista de targets WoL", "category": "system"},
            "wol_list_targets": {"desc": "Lista las MAC configuradas para WoL al conectar cargador", "category": "system"},
            "web_search": {"desc": "Buscar en la web (DuckDuckGo, sin API key)", "category": "web"},
            "web_weather": {"desc": "Consultar el clima de una ciudad (wttr.in, sin API key)", "category": "web"},
            "web_automation": {"desc": "Automatizacion de navegador con Playwright (navegar, click, texto, screenshot)", "category": "web"},
            "files_list": {"desc": "Listar contenido de un directorio local", "category": "files"},
            "files_read": {"desc": "Leer el contenido de un archivo local", "category": "files"},
            "files_write": {"desc": "Escribir contenido a un archivo local", "category": "files"},
            "wol_send": {"desc": "Envia magic packet Wake-on-LAN para prender otra PC", "category": "system"},
            "desktop_tray_start": {"desc": "Inicia icono de bandeja del sistema (pystray)", "category": "desktop"},
            "desktop_tray_stop": {"desc": "Detiene icono de bandeja del sistema", "category": "desktop"},
            "desktop_tray_status": {"desc": "Estado del icono de bandeja", "category": "desktop"},
            "desktop_tray_notify": {"desc": "Muestra notificacion de escritorio desde la bandeja", "category": "desktop"},
            "desktop_hotkey_register": {"desc": "Registra un hotkey global (modulo keyboard)", "category": "desktop"},
            "desktop_hotkey_unregister": {"desc": "Elimina un hotkey global registrado", "category": "desktop"},
            "desktop_hotkey_list": {"desc": "Lista hotkeys globales registrados", "category": "desktop"},
            "desktop_hotkey_start": {"desc": "Inicia escucha de hotkeys globales", "category": "desktop"},
            "desktop_hotkey_stop": {"desc": "Detiene escucha de hotkeys globales", "category": "desktop"},
            "android_create_project": {"desc": "Crea un proyecto Android completo (Gradle, Kotlin, Manifest, layouts, recursos) para Android Studio", "category": "android"},
            "android_project_info": {"desc": "Información completa de un proyecto Android: estructura, archivos, meta, permisos, dependencias", "category": "android"},
            "android_list_projects": {"desc": "Lista todos los proyectos Android creados por ARIA", "category": "android"},
            "android_add_activity": {"desc": "Agrega una Activity + layout a un proyecto Android", "category": "android"},
            "android_add_fragment": {"desc": "Agrega un Fragment a un proyecto Android", "category": "android"},
            "android_add_viewmodel": {"desc": "Agrega un ViewModel a un proyecto Android", "category": "android"},
            "android_add_permission": {"desc": "Agrega un permiso al AndroidManifest.xml", "category": "android"},
            "android_add_dependency": {"desc": "Agrega una dependencia Gradle a app/build.gradle", "category": "android"},
            "android_read_file": {"desc": "Lee cualquier archivo de un proyecto Android", "category": "android"},
            "android_write_file": {"desc": "Escribe/crea cualquier archivo en un proyecto Android", "category": "android"},
            "android_modify_file": {"desc": "Reemplaza texto en cualquier archivo de un proyecto Android", "category": "android"},
            "android_generate_gradle_wrapper": {"desc": "Genera/configura el wrapper de Gradle (gradlew) para compilar", "category": "android"},
            "android_build_apk": {"desc": "Compila un APK (debug/release) con Gradle", "category": "android"},
            "android_install_apk": {"desc": "Instala el APK compilado en dispositivo vía adb", "category": "android"},
            "adb_wireless": {"desc": "ADB inalambrico: conectar, instalar, lanzar apps propias y abrirlas como desktop", "category": "android"},
            "media_extract_video": {"desc": "Extrae TODA la info de un video (yt-dlp, sin descargarlo): metadatos, capítulos, subtítulos, formatos", "category": "media"},
            "media_extract_web": {"desc": "Extrae TODA la info de un sitio web: título, meta, contenido, encabezados, enlaces, imágenes", "category": "media"},
            "media_extract_transcript": {"desc": "Extrae la transcripción/subtítulos completos de un video", "category": "media"},
            "media_extract_all": {"desc": "Extrae video + transcripción (o web) de un link automáticamente", "category": "media"},
        }
        logger.info(f"Skills cargadas: {len(self._skills)}")

    def process(self, req_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        handlers = {
            "chat": lambda: self._handle_chat(data),
            "skill": lambda: self._handle_skill(data),
            "tool": lambda: self._handle_tool(data),
            "list_skills": lambda: self._handle_list_skills(),
            "status": lambda: self._handle_status(),
            "ping": lambda: {"status": "ok", "type": "pong"},
        }
        handler = handlers.get(req_type)
        if handler:
            try:
                return handler()
            except Exception as exc:
                logger.error(f"Logic error ({req_type}): {exc}")
                return {"status": "error", "error": str(exc)}
        return {"status": "error", "error": f"tipo desconocido: {req_type}"}

    def _handle_chat(self, data: Dict[str, Any]) -> Dict[str, Any]:
        message = str(data.get("message", "")).strip()
        if not message:
            return {"status": "error", "error": "mensaje vacío"}
        result = self.ai.chat(
            message=message,
            history=data.get("history", []),
            system_prompt=data.get("system_prompt"),
            temperature=float(data.get("temperature", 0.7)),
            max_tokens=int(data.get("max_tokens", 1024)),
        )
        # Capa Mnemosyne: buffer operativo de la sesion actual.
        self._record_in_mnemosyne("user", message)
        self._record_in_mnemosyne("assistant", str(result.get("response", "")))
        return {"status": "ok", "response": result["response"],
                "provider": result["provider"], "latency": result["latency"]}

    def _record_in_mnemosyne(self, role: str, content: str) -> None:
        """Guarda un turno en Mnemosyne sin romper el chat si falla."""
        text = (content or "").strip()
        if not text:
            return
        try:
            self.mnemosyne.add(role=role, content=text[:4000], importance=0.5)
        except Exception as exc:
            logger.debug(f"Mnemosyne: no se pudo registrar el turno: {exc}")

    def _handle_skill(self, data: Dict[str, Any]) -> Dict[str, Any]:
        name = str(data.get("skill", "")).strip()
        params = data.get("params", {}) or {}
        if name == "drive":
            return {"status": "ok",
                    "message": "Visión autónoma de Drive: procesa medios de Google Drive con ARIA Eyes (modelo local). Se ejecuta al arranque del backend."}
        if name == "net_scan":
            return self._skill_net_scan(params)
        if name == "wifi_scan":
            return self._skill_wifi_scan(params)
        if name == "mac_spoof":
            return self._skill_mac_spoof(params)
        if name == "tor_status":
            return self._skill_tor_status(params)
        if name == "whois_lookup":
            return self._skill_whois_lookup(params)
        if name == "packet_capture":
            return self._skill_packet_capture(params)
        if name == "kali_care":
            return self._skill_kali_care(params)
        if name == "nmap_full":
            return self._skill_nmap_full(params)
        if name == "metasploit":
            return self._skill_metasploit(params)
        if name == "drive_analyze":
            return self._skill_drive_analyze(params)
        if name == "creative_ideas":
            return self._skill_creative_ideas(params)
        if name == "auto_improve":
            return self._skill_auto_improve(params)
        if name == "autonomo_start":
            return self._skill_autonomo_start(params)
        if name == "autonomo_stop":
            return self._skill_autonomo_stop(params)
        if name == "instagram_video":
            return self._skill_media_view(params)
        if name == "media_view":
            return self._skill_media_view(params)
        if name == "media_related":
            return self._skill_media_related(params)
        if name == "instagram_re":
            return self._skill_instagram_re(params)
        if name == "rag_retrieve":
            return self._skill_rag_retrieve(params)
        if name == "rag_add":
            return self._skill_rag_add(params)
        if name == "memory_add":
            return self._skill_memory_add(params)
        if name == "memory_search":
            return self._skill_memory_search(params)
        if name == "memory_consolidate":
            return self._skill_memory_consolidate(params)
        if name == "memory_stats":
            return self._skill_memory_stats(params)
        if name == "memory_layers":
            return self._skill_memory_layers(params)
        if name == "mnemosyne_add":
            return self._skill_mnemosyne_add(params)
        if name == "mnemosyne_search":
            return self._skill_mnemosyne_search(params)
        if name == "hindsight_reflect":
            return self._skill_hindsight_reflect(params)
        if name == "hindsight_insights":
            return self._skill_hindsight_insights(params)
        if name == "hindsight_context":
            return self._skill_hindsight_context(params)
        if name == "wiki_write":
            return self._skill_wiki_write(params)
        if name == "wiki_read":
            return self._skill_wiki_read(params)
        if name == "wiki_search":
            return self._skill_wiki_search(params)
        if name == "process_guard_status":
            return self._skill_process_guard_status(params)
        if name == "process_list":
            return self._skill_process_list(params)
        if name == "process_terminate":
            return self._skill_process_terminate(params)
        if name == "ai_models":
            return self._skill_ai_models(params)
        if name == "ai_train":
            return self._skill_ai_train(params)
        if name == "ai_train_status":
            return self._skill_ai_train_status(params)
        if name == "ai_improve":
            return self._skill_ai_improve(params)
        if name == "env_start":
            return self._skill_env_start(params)
        if name == "env_stop":
            return self._skill_env_stop(params)
        if name == "env_process":
            return self._skill_env_process(params)
        if name == "env_status":
            return self._skill_env_status(params)
        if name == "env_list":
            return self._skill_env_list(params)
        if name == "sandbox_exec":
            return self._skill_sandbox_exec(params)
        if name == "sandbox_skill":
            return self._skill_sandbox_skill(params)
        if name == "sandbox_status":
            return self._skill_sandbox_status(params)
        if name == "sandbox_stop":
            return self._skill_sandbox_stop(params)
        if name == "sandbox_list":
            return self._skill_sandbox_list(params)
        if name == "discord_connect":
            return self._skill_discord_connect(params)
        if name == "discord_disconnect":
            return self._skill_discord_disconnect(params)
        if name == "discord_status":
            return self._skill_discord_status(params)
        if name == "discord_guilds":
            return self._skill_discord_guilds(params)
        if name == "discord_channels":
            return self._skill_discord_channels(params)
        if name == "discord_send":
            return self._skill_discord_send(params)
        if name == "discord_read":
            return self._skill_discord_read(params)
        if name == "github_list_repos":
            return self._skill_github_list_repos(params)
        if name == "github_search_repos":
            return self._skill_github_search_repos(params)
        if name == "github_get_repo":
            return self._skill_github_get_repo(params)
        if name == "github_file_content":
            return self._skill_github_file_content(params)
        if name == "github_list_dir":
            return self._skill_github_list_dir(params)
        if name == "github_issues":
            return self._skill_github_issues(params)
        if name == "github_auth":
            return self._skill_github_auth(params)
        if name == "power_status":
            return self._skill_power_status(params)
        if name == "power_wake_on_ac_info":
            return self._skill_power_wake_on_ac_info(params)
        if name == "wol_send":
            return self._skill_wol_send(params)
        if name == "power_monitor_start":
            return self._skill_power_monitor_start(params)
        if name == "power_monitor_stop":
            return self._skill_power_monitor_stop(params)
        if name == "power_monitor_status":
            return self._skill_power_monitor_status(params)
        if name == "wol_add_target":
            return self._skill_wol_add_target(params)
        if name == "wol_remove_target":
            return self._skill_wol_remove_target(params)
        if name == "wol_list_targets":
            return self._skill_wol_list_targets(params)
        if name == "web_search":
            return self._skill_web_search(params)
        if name == "web_weather":
            return self._skill_web_weather(params)
        if name == "web_automation":
            return self._skill_web_automation(params)
        if name == "files_list":
            return self._skill_files_list(params)
        if name == "files_read":
            return self._skill_files_read(params)
        if name == "files_write":
            return self._skill_files_write(params)
        if name == "android_create_project":
            return self._skill_android_create_project(params)
        if name == "android_project_info":
            return self._skill_android_project_info(params)
        if name == "android_list_projects":
            return self._skill_android_list_projects(params)
        if name == "android_add_activity":
            return self._skill_android_add_activity(params)
        if name == "android_add_fragment":
            return self._skill_android_add_fragment(params)
        if name == "android_add_viewmodel":
            return self._skill_android_add_viewmodel(params)
        if name == "android_add_permission":
            return self._skill_android_add_permission(params)
        if name == "android_add_dependency":
            return self._skill_android_add_dependency(params)
        if name == "android_read_file":
            return self._skill_android_read_file(params)
        if name == "android_write_file":
            return self._skill_android_write_file(params)
        if name == "android_modify_file":
            return self._skill_android_modify_file(params)
        if name == "android_generate_gradle_wrapper":
            return self._skill_android_generate_gradle_wrapper(params)
        if name == "android_build_apk":
            return self._skill_android_build_apk(params)
        if name == "android_install_apk":
            return self._skill_android_install_apk(params)
        if name == "adb_wireless":
            return self._skill_adb_wireless(params)
        if name == "media_extract_video":
            return self._skill_media_extract_video(params)
        if name == "media_extract_web":
            return self._skill_media_extract_web(params)
        if name == "media_extract_transcript":
            return self._skill_media_extract_transcript(params)
        if name == "media_extract_all":
            return self._skill_media_extract_all(params)
        if name == "desktop_tray_start":
            return self._skill_desktop_tray_start(params)
        if name == "desktop_tray_stop":
            return self._skill_desktop_tray_stop(params)
        if name == "desktop_tray_status":
            return self._skill_desktop_tray_status(params)
        if name == "desktop_tray_notify":
            return self._skill_desktop_tray_notify(params)
        if name == "desktop_hotkey_register":
            return self._skill_desktop_hotkey_register(params)
        if name == "desktop_hotkey_unregister":
            return self._skill_desktop_hotkey_unregister(params)
        if name == "desktop_hotkey_list":
            return self._skill_desktop_hotkey_list(params)
        if name == "desktop_hotkey_start":
            return self._skill_desktop_hotkey_start(params)
        if name == "desktop_hotkey_stop":
            return self._skill_desktop_hotkey_stop(params)
        if name in self._skills:
            return {"status": "ok", "skill": name, "desc": self._skills[name]["desc"]}
        return {"status": "error", "error": f"skill no encontrada: {name}"}

    def _run_cmd(self, cmd: List[str], timeout: int = 15) -> Dict[str, Any]:
        """Ejecuta un comando de forma segura con timeout y validación."""
        if not cmd:
            return {"status": "error", "error": "comando vacío"}
        binary = shutil.which(cmd[0])
        if not binary:
            return {"status": "error", "error": f"binario no encontrado: {cmd[0]}"}
        try:
            proc = subprocess.run(
                [binary] + cmd[1:],
                capture_output=True, text=True, timeout=timeout,
            )
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            return {
                "status": "ok" if proc.returncode == 0 else "error",
                "returncode": proc.returncode,
                "output": out,
                "stderr": err,
                "command": " ".join(cmd),
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": f"timeout ({timeout}s): {' '.join(cmd)}",
                    "command": " ".join(cmd)}
        except Exception as exc:
            return {"status": "error", "error": str(exc), "command": " ".join(cmd)}

    def _skill_net_scan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        target = str(params.get("target", "192.168.1.0/24")).strip()
        # Validación básica: solo permitir rangos/hosts simples (sin shell metacaracteres)
        import re
        if not re.match(r"^[\w\.\-/]+$", target):
            return {"status": "error", "error": "target no válido"}
        return self._run_cmd(["nmap", "-sn", "--disable-arp-ping", target], timeout=30)

    def _skill_wifi_scan(self, params: Dict[str, Any]) -> Dict[str, Any]:
        iface = str(params.get("iface", "")).strip()
        if shutil.which("nmcli"):
            cmd = ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"]
            if iface:
                cmd += ["--device", iface]
            return self._run_cmd(cmd, timeout=15)
        if shutil.which("iwlist"):
            dev = iface or "wlan0"
            return self._run_cmd(["iwlist", dev, "scan"], timeout=15)
        return {"status": "error", "error": "ni nmcli ni iwlist disponibles"}

    def _skill_mac_spoof(self, params: Dict[str, Any]) -> Dict[str, Any]:
        iface = str(params.get("iface", "")).strip()
        if not iface:
            return {"status": "error", "error": "iface requerida"}
        import re
        if not re.match(r"^[\w\-]+$", iface):
            return {"status": "error", "error": "iface no válida"}
        down = self._run_cmd(["ip", "link", "set", iface, "down"], timeout=5)
        if down["status"] != "ok":
            return down
        spoof = self._run_cmd(["macchanger", "-r", iface], timeout=10)
        up = self._run_cmd(["ip", "link", "set", iface, "up"], timeout=5)
        return spoof

    def _skill_tor_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._run_cmd(["systemctl", "is-active", "tor"], timeout=5)

    def _skill_whois_lookup(self, params: Dict[str, Any]) -> Dict[str, Any]:
        domain = str(params.get("domain", "")).strip()
        if not domain:
            return {"status": "error", "error": "domain requerida"}
        import re
        if not re.match(r"^[\w\.\-]+$", domain):
            return {"status": "error", "error": "domain no válida"}
        return self._run_cmd(["whois", domain], timeout=15)

    def _skill_packet_capture(self, params: Dict[str, Any]) -> Dict[str, Any]:
        iface = str(params.get("iface", "eth0")).strip()
        count = int(params.get("count", 10))
        import re
        if not re.match(r"^[\w\-]+$", iface):
            return {"status": "error", "error": "iface no válida"}
        if count < 1 or count > 1000:
            return {"status": "error", "error": "count fuera de rango (1-1000)"}
        return self._run_cmd(["tcpdump", "-i", iface, "-c", str(count), "-n"], timeout=30)

    def _skill_kali_care(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mantenimiento y diagnóstico de seguridad del entorno Kali (estilo KaliCare).

        Ejecuta chequeos de estado del sistema, servicios críticos, firewall,
        Ollama y limpieza de caché. Sin modificar configuración del usuario.
        """
        results: Dict[str, Any] = {}

        # 1. Estado del sistema (CPU/RAM/disco)
        results["sistema"] = self._run_cmd(["bash", "-c",
            "echo 'CPU:'; top -bn1 | grep 'Cpu(s)' | awk '{print $2}'; "
            "echo 'RAM:'; free -h | grep Mem | awk '{print $3\" / \"$2}'; "
            "echo 'DISCO:'; df -h / | tail -1 | awk '{print $3\" / \"$2\" (\"$5\")\"}'"], timeout=10)

        # 2. Servicios críticos de ARIA
        results["servicios_aria"] = self._run_cmd(["systemctl", "is-active", "aria-os"], timeout=5)
        results["servicios_ollama"] = self._run_cmd(["systemctl", "is-active", "ollama"], timeout=5)

        # 3. Firewall nftables
        results["firewall"] = self._run_cmd(["nft", "list", "ruleset"], timeout=10)

        # 4. Puertos abiertos
        results["puertos"] = self._run_cmd(["ss", "-tlnp"], timeout=5)

        # 5. Proceso ARIA
        results["proceso_aria"] = self._run_cmd(["pgrep", "-a", "aria_native"], timeout=5)

        # 6. Procesos con flags de depuración expuestos (riesgo de escalada de privilegios)
        #    Lección HTB "Reactor": Node.js con --inspect expuesto como root permite escalada.
        results["procesos_depuracion"] = self._run_cmd(["bash", "-c",
            "hallados=0; "
            "for f in /proc/[0-9]*/cmdline; do "
            "  pid=$(basename $(dirname \"$f\")); "
            "  cmd=$(tr '\\0' ' ' < \"$f\" 2>/dev/null); "
            "  if echo \"$cmd\" | grep -qE -- '--inspect|--debug|--debug-brk|--inspect-brk'; then "
            "    echo \"PID=$pid: $cmd\"; hallados=1; "
            "  fi; "
            "done; "
            "if [ $hallados -eq 0 ]; then echo \"ninguno\"; fi"], timeout=10)

        # 7. Ollama disponible
        import urllib.request
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
                models = [m.get("name", "?") for m in data.get("models", [])]
                results["ollama_modelos"] = {"status": "ok", "modelos": models}
        except Exception as exc:
            results["ollama_modelos"] = {"status": "error", "error": str(exc)}

        # 7. Limpieza de caché APT (sólo listar, no borrar sin confirmación)
        results["cache_apt"] = self._run_cmd(["du", "-sh", "/var/cache/apt/archives"], timeout=10)

        # Resumen de estado
        todo_ok = all(
            r.get("status") == "ok" for r in results.values()
            if isinstance(r, dict) and "status" in r
        )

        return {
            "status": "ok" if todo_ok else "advertencia",
            "skill": "kali_care",
            "desc": "Diagnóstico de mantenimiento y seguridad del entorno Kali",
            "resultados": results,
        }

    def _skill_nmap_full(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Escaneo completo de puertos y servicios con nmap (-sS -sV -O).

        Solo reconocimiento pasivo/activo sin explotación.
        """
        target = str(params.get("target", "")).strip()
        import re
        if not target:
            return {"status": "error", "error": "target requerida"}
        if not re.match(r"^[\w\.\-/]+$", target):
            return {"status": "error", "error": "target no válida (solo alfanumérico, punto, guion, barra)"}
        # Escaneo SYN + detección de versión + SO (requiere root para -sS/-O, pero intentamos)
        return self._run_cmd(["nmap", "-sS", "-sV", "-O", "--version-intensity", "5", target], timeout=60)

    def _skill_metasploit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Reconocimiento y generación de payload con Metasploit (SOLO LECTURA).

        Acciones permitidas:
        - action=list_payloads: lista payloads disponibles (msfvenom --list payloads)
        - action=search_modulo: busca módulos (msfconsole -q -x "search <termino>")
        - action=info_modulo: información de un módulo (msfconsole -q -x "info <modulo>")

        NO se permite ejecutar exploits, crear sesiones ni generar payloads ejecutables.
        """
        action = str(params.get("action", "list_payloads")).strip()
        if action not in ("list_payloads", "search_modulo", "info_modulo"):
            return {"status": "error", "error": "acción no permitida (list_payloads, search_modulo, info_modulo)"}

        if action == "list_payloads":
            return self._run_cmd(["msfvenom", "--list", "payloads"], timeout=30)

        term = str(params.get("termino", "")).strip()
        if not term:
            return {"status": "error", "error": "termino requerido para search_modulo/info_modulo"}
        import re
        if not re.match(r"^[\w\/\.\-]+$", term):
            return {"status": "error", "error": "termino no válido (solo alfanumérico, barra, punto, guion)"}

        if action == "search_modulo":
            return self._run_cmd(["msfconsole", "-q", "-x", f"search {term}; exit"], timeout=30)
        if action == "info_modulo":
            return self._run_cmd(["msfconsole", "-q", "-x", f"info {term}; exit"], timeout=30)

        return {"status": "error", "error": "acción no implementada"}

    # ─── Skill: media_view — ver cualquier video/media SIN descargar ──────────

    def _skill_media_view(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae información detallada de cualquier video/media (YouTube, TikTok,
        Instagram, Vimeo, etc.) SIN descargar el archivo.

        Estrategia:
        1. yt-dlp --dump-single-json --skip-download (metadatos completos,
           todos los formatos, miniatura de mayor resolución, comentarios)
        2. Fallback oembed si yt-dlp falla
        3. Fallback HTML scraping (og:*) si oembed falla
        4. Descarga SOLO la miniatura (frame representativo) y la describe con
           Ollama visión (granite3.2-vision:2b) de forma minuciosa
        5. Acceso al video con Range pequeño para confirmar stream legible
           (sin guardar el archivo entero)
        6. Clasificación de uso con JEV (decisión tipada)
        7. Guarda informe JSON detallado en instagram/descriptions/
        """
        url = str(params.get("url", "")).strip()
        if not url:
            return {"status": "error", "error": "url requerida"}

        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()

        desc_dir = ARIA_APP / "instagram" / "descriptions"
        desc_dir.mkdir(parents=True, exist_ok=True)

        result: Dict[str, Any] = {
            "status": "ok",
            "skill": "media_view",
            "url": url,
            "host": host,
            "timestamp": time.time(),
            "method": "no-download",
        }

        import re as _re

        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/120.0 Safari/537.36")

        # ══════════════════════════════════════════════════════════════════
        # 1. Metadatos completos con yt-dlp (--dump-single-json --skip-download)
        # ═══════════════════════════════════════════════════════════════════
        ytdlp_meta: Dict[str, Any] = {}
        ytdlp_bin = shutil.which("yt-dlp") or shutil.which("youtube-dl")
        venv_yt_dlp = ARIA_APP.parent / ".venv" / "Scripts" / "yt-dlp.exe"
        ytdlp_cmd: List[str] = []
        if ytdlp_bin:
            ytdlp_cmd = [ytdlp_bin]
        elif venv_yt_dlp.exists():
            ytdlp_cmd = [str(venv_yt_dlp)]
        else:
            ytdlp_cmd = [sys.executable, "-m", "yt_dlp"]
        ytdlp = ytdlp_cmd[0] if ytdlp_cmd else None

        if ytdlp_cmd:
            try:
                proc = subprocess.run(
                    ytdlp_cmd + ["--dump-single-json", "--no-playlist", "--no-warnings",
                                 "--skip-download", url],
                    capture_output=True, text=True, timeout=90,
                )
                if proc.returncode == 0:
                    ytdlp_meta = json.loads(proc.stdout or "{}")
                else:
                    ytdlp_meta = {"error": f"yt-dlp exit {proc.returncode}",
                                  "stderr": proc.stderr[:500] if proc.stderr else ""}
            except Exception as exc:
                ytdlp_meta = {"error": str(exc)}
        result["ytdlp_meta_error"] = ytdlp_meta.get("error") if ytdlp_meta.get("error") else None
        result["ytdlp_meta"] = {k: v for k, v in ytdlp_meta.items()
                                if k not in ("formats", "thumbnails", "comments",
                                             "requested_downloads", "http_headers")}

        # ═══════════════════════════════════════════════════════════════════
        # 2. Extraer metadatos estructurados de yt-dlp
        # ════════════════════════════════════════════════════════════════════
        meta: Dict[str, Any] = {}
        if ytdlp_meta and not ytdlp_meta.get("error"):
            meta["title"] = ytdlp_meta.get("title", "")
            meta["fulltitle"] = ytdlp_meta.get("fulltitle", "")
            meta["description"] = ytdlp_meta.get("description", "") or ""
            meta["author"] = ytdlp_meta.get("uploader", ytdlp_meta.get("channel", ""))
            meta["uploader_id"] = ytdlp_meta.get("uploader_id", "")
            meta["uploader_url"] = ytdlp_meta.get("uploader_url", "")
            meta["channel_id"] = ytdlp_meta.get("channel_id", "")
            meta["channel_url"] = ytdlp_meta.get("channel_url", "")
            meta["channel_follower_count"] = ytdlp_meta.get("channel_follower_count", 0)
            meta["duration"] = ytdlp_meta.get("duration", 0)
            meta["duration_string"] = ytdlp_meta.get("duration_string", "")
            meta["release_year"] = ytdlp_meta.get("release_year", "")
            meta["age_limit"] = ytdlp_meta.get("age_limit", 0)
            meta["is_live"] = ytdlp_meta.get("is_live", False)
            meta["was_live"] = ytdlp_meta.get("was_live", False)
            meta["dislike_count"] = ytdlp_meta.get("dislike_count", 0)
            meta["average_rating"] = ytdlp_meta.get("average_rating", 0)
            meta["tags"] = ytdlp_meta.get("tags", []) or []
            meta["categories"] = ytdlp_meta.get("categories", []) or []
            meta["playable_in_embed"] = ytdlp_meta.get("playable_in_embed", False)
            meta["location"] = ytdlp_meta.get("location", "")
            meta["view_count"] = ytdlp_meta.get("view_count", 0)
            meta["like_count"] = ytdlp_meta.get("like_count", 0)
            meta["comment_count"] = ytdlp_meta.get("comment_count", 0)
            meta["upload_date"] = ytdlp_meta.get("upload_date", "")
            meta["modified_date"] = ytdlp_meta.get("modified_date", "")
            meta["modified_timestamp"] = ytdlp_meta.get("modified_timestamp", 0)
            meta["extractor"] = ytdlp_meta.get("extractor", "")
            meta["id"] = ytdlp_meta.get("id", "")
            meta["webpage_url"] = ytdlp_meta.get("webpage_url", url)
            meta["webpage_url_basename"] = ytdlp_meta.get("webpage_url_basename", "")
            meta["webpage_url_domain"] = ytdlp_meta.get("webpage_url_domain", "")
            meta["display_id"] = ytdlp_meta.get("display_id", "")
            meta["extractor_key"] = ytdlp_meta.get("extractor_key", "")
            meta["playlist"] = ytdlp_meta.get("playlist", "")
            meta["playlist_index"] = ytdlp_meta.get("playlist_index", "")
            meta["playlist_title"] = ytdlp_meta.get("playlist_title", "")
            meta["playlist_id"] = ytdlp_meta.get("playlist_id", "")
            meta["resolution"] = ytdlp_meta.get("resolution", "")
            meta["aspect_ratio"] = ytdlp_meta.get("aspect_ratio", 0)
            # Mejor miniatura: la de mayor resolución disponible
            thumbs = ytdlp_meta.get("thumbnails", []) or []
            best_thumb = ""
            best_res = 0
            for t in thumbs:
                w = t.get("width") or 0
                h = t.get("height") or 0
                res = w * h
                if res > best_res and t.get("url"):
                    best_res = res
                    best_thumb = t["url"]
            meta["image"] = best_thumb or ytdlp_meta.get("thumbnail", "")
            meta["thumbnail_width"] = (next((t.get("width") for t in thumbs
                                             if t.get("url") == best_thumb), 0))
            meta["thumbnail_height"] = (next((t.get("height") for t in thumbs
                                              if t.get("url") == best_thumb), 0))
            # Mejor URL de video directa (preferir la de mayor calidad con video+audio)
            formats = ytdlp_meta.get("formats", []) or []
            video_formats = [f for f in formats if f.get("vcodec") and f.get("vcodec") != "none"]
            if video_formats:
                best_vid = max(video_formats,
                               key=lambda f: (f.get("height") or 0) * (f.get("width") or 0))
                meta["video_url"] = best_vid.get("url", "")
                meta["video_width"] = best_vid.get("width", 0)
                meta["video_height"] = best_vid.get("height", 0)
                meta["video_codec"] = best_vid.get("vcodec", "")
                meta["video_bitrate"] = best_vid.get("vbr", 0)
                meta["video_fps"] = best_vid.get("fps", 0)
                meta["video_ext"] = best_vid.get("ext", "")
                meta["video_format_id"] = best_vid.get("format_id", "")
                meta["video_dynamic_range"] = best_vid.get("dynamic_range", "")
                # Info de todos los formatos disponibles (para el informe)
                meta["all_formats"] = [
                    {
                        "format_id": f.get("format_id", ""),
                        "ext": f.get("ext", ""),
                        "resolution": f.get("resolution", ""),
                        "width": f.get("width", 0),
                        "height": f.get("height", 0),
                        "vcodec": f.get("vcodec", ""),
                        "acodec": f.get("acodec", ""),
                        "vbr": f.get("vbr", 0),
                        "abr": f.get("abr", 0),
                        "fps": f.get("fps", 0),
                        "dynamic_range": f.get("dynamic_range", ""),
                        "format_note": f.get("format_note", ""),
                    }
                    for f in formats[:20]
                ]
            else:
                meta["video_url"] = ytdlp_meta.get("url", "")
                meta["video_width"] = ytdlp_meta.get("width", 0)
                meta["video_height"] = ytdlp_meta.get("height", 0)
                meta["all_formats"] = []

        # Subtítulos y subtítulos automáticos (para transcripción futura)
        subs = ytdlp_meta.get("subtitles", {}) or {}
        auto_subs = ytdlp_meta.get("automatic_captions", {}) or {}
        meta["subtitle_languages"] = list(subs.keys())
        meta["auto_caption_languages"] = list(auto_subs.keys())

        # Capítulos / segmentos del video (para navegación por tiempo)
        chapters = ytdlp_meta.get("chapters", []) or []
        meta["chapters"] = [
            {"start_time": c.get("start_time", 0),
             "end_time": c.get("end_time", 0),
             "title": c.get("title", ""),
             "start_timestamp": c.get("start_timestamp", ""),
             "end_timestamp": c.get("end_timestamp", "")}
            for c in chapters[:20]
        ]

        # ════════════════════════════════════════════════════════════════════
        # 2b. Análisis de comentarios (sentido, temas, top comentarios)
        # ══════════════════════════════════════════════════════════════════════
        comments = ytdlp_meta.get("comments", []) or []
        meta["comments_analyzed"] = self._analyze_comments(comments)


        # ═══════════════════════════════════════════════════════════════════
        # 3. Fallback: oembed (sin autenticación)
        # ════════════════════════════════════════════════════════════════════
        oembed: Dict[str, Any] = {}
        if not meta.get("title") or not meta.get("image"):
            try:
                import urllib.request, urllib.parse
                oembed_url = "https://api.instagram.com/oembed?url=" + urllib.parse.quote(url, safe="")
                req = urllib.request.Request(oembed_url, headers={"User-Agent": ua})
                with urllib.request.urlopen(req, timeout=20) as r:
                    oembed = json.loads(r.read().decode("utf-8", errors="ignore"))
            except Exception:
                oembed = {}
        if oembed and not oembed.get("error"):
            meta.setdefault("title", oembed.get("title", ""))
            meta.setdefault("author", oembed.get("author_name", ""))
            meta.setdefault("image", oembed.get("thumbnail_url", ""))
            meta.setdefault("html_embed", oembed.get("html", ""))
            meta.setdefault("provider", oembed.get("provider_name", ""))
        result["oembed"] = oembed

        # ════════════════════════════════════════════════════════════════════
        # 4. Fallback: scraping HTML para Open Graph (últimos recursos)
        # ═════════════════════════════════════════════════════════════════════
        if not meta.get("video_url") or not meta.get("title"):
            html = ""
            try:
                import urllib.request
                req = urllib.request.Request(url, headers={"User-Agent": ua})
                with urllib.request.urlopen(req, timeout=25) as r:
                    html = r.read().decode("utf-8", errors="ignore")
                for tag in ("og:title", "og:description", "og:image", "og:video",
                            "og:type", "og:site_name", "og:video:width", "og:video:height",
                            "og:video:type", "og:video:duration", "og:video:actors",
                            "og:video:director", "og:video:series", "og:video:release_date",
                            "og:video:tag", "og:audio", "og:determiner", "og:locale",
                            "og:locale:alternate"):
                    m = _re.search(r'<meta\s+property=["\']' + tag + r'["\']\s+content=["\']([^"\']+)["\']', html)
                    if m:
                        key = tag.split(":")[1]
                        meta.setdefault(key, m.group(1))
                mv = _re.search(r'"video_url"\s*:\s*"([^"]+)"', html)
                if mv:
                    meta.setdefault("video_url", mv.group(1).replace("\\u0026", "&"))
                meta["html_length"] = len(html)

                # Twitter Cards
                for tag in ("twitter:title", "twitter:description", "twitter:image",
                            "twitter:player", "twitter:player:width", "twitter:player:height",
                            "twitter:site", "twitter:creator", "twitter:card"):
                    m = _re.search(r'<meta\s+(?:name|property)=["\']' + tag + r'["\']\s+content=["\']([^"\']+)["\']', html)
                    if m:
                        key = tag.split(":")[1]
                        meta.setdefault("twitter_" + key, m.group(1))

                # JSON-LD estructurado
                meta["json_ld"] = self._extract_json_ld(html)

            except Exception as exc:
                meta["html_error"] = str(exc)

        result["metadata"] = meta

        # ════════════════════════════════════════════════════════════════════
        # 5. Descargar SOLO la miniatura (frame representativo) y describir
        #    con Ollama visión de forma minuciosa
        # ═════════════════════════════════════════════════════════════════════
        thumb_path = None
        thumb_url = meta.get("image", "")
        if thumb_url:
            try:
                import urllib.request as ulreq
                thumb_path = desc_dir / f"thumb_{int(time.time())}.jpg"
                ulreq.urlretrieve(thumb_url, str(thumb_path))
                result["thumbnail"] = str(thumb_path)
                result["thumbnail_url"] = thumb_url
                result["thumbnail_method"] = "urllib"
                result["thumbnail_width"] = meta.get("thumbnail_width", 0)
                result["thumbnail_height"] = meta.get("thumbnail_height", 0)
            except Exception as exc:
                result["thumbnail_error"] = str(exc)

        # Fallback: yt-dlp --write-thumbnail --skip-download
        if not thumb_path and ytdlp:
            try:
                thumb_out = str(desc_dir / f"thumb_{int(time.time())}")
                proc = subprocess.run(
                    [ytdlp, "--write-thumbnail", "--skip-download", "--no-playlist",
                     "--no-warnings", "-o", thumb_out, url],
                    capture_output=True, text=True, timeout=60,
                )
                if proc.returncode == 0:
                    import glob as _glob
                    thumbs = _glob.glob(thumb_out + ".*")
                    if thumbs:
                        thumb_path = Path(thumbs[0])
                        result["thumbnail"] = str(thumb_path)
                        result["thumbnail_method"] = "yt-dlp"
            except Exception as exc:
                result["thumbnail_ytdlp_error"] = str(exc)

        visual_description = ""
        if thumb_path:
            try:
                visual_description = self._describe_image_with_ollama(str(thumb_path))
                result["visual_description"] = visual_description
            except Exception as exc:
                result["visual_description"] = f"Visión no disponible: {exc}"
        else:
            result["visual_description"] = "Sin miniatura disponible para visión."

        # ════════════════════════════════════════════════════════════════════
        # 6. Acceso al video con Range pequeño (confirmar stream legible)
        # ═════════════════════════════════════════════════════════════════════
        video_url = meta.get("video_url", "")
        if video_url:
            result["video_url"] = video_url
            try:
                import urllib.request
                req = urllib.request.Request(video_url, headers={
                    "User-Agent": ua,
                    "Range": "bytes=0-262143",  # solo los primeros 256 KB
                })
                with urllib.request.urlopen(req, timeout=20) as r:
                    chunk = r.read(65536)  # leer 64 KB para confirmar que es video
                    result["video_accessible"] = True
                    result["video_status"] = r.status
                    result["video_content_type"] = r.headers.get("Content-Type", "")
                    result["video_first_bytes"] = len(chunk)
                    result["video_note"] = "Stream accesible (sin descarga completa)"
            except Exception as exc:
                result["video_accessible"] = False
                result["video_error"] = str(exc)[:200]
        else:
            result["video_accessible"] = None
            result["video_note"] = "No se encontró URL directa del video"

        # ════════════════════════════════════════════════════════════════════
        # 7. Clasificación de uso con JEV (decisión tipada)
        # ═════════════════════════════════════════════════════════════════════
        jev_decision = self._jev_classify_usage(meta, result.get("visual_description", ""))
        result["jev"] = jev_decision

        # ═════════════════════════════════════════════════════════════════════
        # 8. Análisis de compatibilidad con ARIA
        # ══════════════════════════════════════════════════════════════════════
        compat = self._analyze_compatibility(meta, result)
        result["compatibilidad"] = compat

        # ═════════════════════════════════════════════════════════════════════
        # 8. Guardar informe JSON detallado
        # ══════════════════════════════════════════════════════════════════════
        safe_name = _re.sub(r"[^a-z0-9]+", "-", (meta.get("title") or "media").lower()).strip("-")[:40]
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_file = desc_dir / f"media_{safe_name}-{ts}.json"
        try:
            report_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            result["report_file"] = str(report_file)
        except Exception as exc:
            result["report_error"] = str(exc)

        # ═════════════════════════════════════════════════════════════════════
        # 9. Resumen legible para el chat (información exacta y entendible)
        # ═══════════════════════════════════════════════════════════════════════
        lines = []
        lines.append(f"📹 Media: {meta.get('title', 'Sin título')}")
        if meta.get("fulltitle") and meta.get("fulltitle") != meta.get("title"):
            lines.append(f"   Título completo: {meta['fulltitle']}")
        lines.append(f"🔗 URL: {url}")
        lines.append(f"🏠 Plataforma: {meta.get('extractor', host)}")
        lines.append(f"👤 Autor: {meta.get('author', 'Desconocido')}")
        if meta.get("uploader_id"):
            lines.append(f"   ID autor: {meta['uploader_id']}")
        if meta.get("channel_follower_count"):
            lines.append(f"   Seguidores canal: {meta['channel_follower_count']:,}")
        if meta.get("duration"):
            lines.append(f"⏱️ Duración: {meta['duration']}s ({meta.get('duration_string','')})")
        if meta.get("release_year"):
            lines.append(f"📅 Año: {meta['release_year']}")
        if meta.get("age_limit"):
            lines.append(f"🔞 Edad límite: {meta['age_limit']}")
        if meta.get("view_count"):
            lines.append(f"👁️ Vistas: {meta['view_count']:,}")
        if meta.get("like_count"):
            lines.append(f"❤️ Likes: {meta['like_count']:,}")
        if meta.get("dislike_count"):
            lines.append(f"💔 Dislikes: {meta['dislike_count']:,}")
        if meta.get("comment_count"):
            lines.append(f"💬 Comentarios: {meta['comment_count']:,}")
        if meta.get("upload_date"):
            lines.append(f"📤 Subido: {meta['upload_date']}")
        if meta.get("modified_date"):
            lines.append(f"🔄 Modificado: {meta['modified_date']}")
        if meta.get("tags"):
            lines.append(f"🏷️ Tags: {', '.join(meta['tags'][:10])}")
        if meta.get("categories"):
            lines.append(f"📂 Categorías: {', '.join(meta['categories'])}")
        if meta.get("description"):
            lines.append(f"📝 Descripción: {meta['description'][:300]}")
        if meta.get("chapters"):
            lines.append(f"📑 Capítulos: {len(meta['chapters'])} segmento(s)")
        if meta.get("video_width") and meta.get("video_height"):
            lines.append(f"📐 Resolución video: {meta['video_width']}x{meta['video_height']}")
        if meta.get("aspect_ratio"):
            lines.append(f"   Aspect ratio: {meta['aspect_ratio']:.2f}")
        if meta.get("video_codec"):
            lines.append(f"🎞️ Codec: {meta['video_codec']}")
        if meta.get("video_bitrate"):
            lines.append(f"📊 Bitrate: {meta['video_bitrate']} kbps")
        if meta.get("video_fps"):
            lines.append(f"   FPS: {meta['video_fps']}")
        if meta.get("video_dynamic_range"):
            lines.append(f"   Rango dinámico: {meta['video_dynamic_range']}")
        if meta.get("subtitle_languages"):
            lines.append(f"💬 Subtítulos: {', '.join(meta['subtitle_languages'][:5])}")
        if meta.get("auto_caption_languages"):
            lines.append(f"   Subtítulos auto: {', '.join(meta['auto_caption_languages'][:5])}")
        if meta.get("playable_in_embed") is not None:
            lines.append(f"   Incrustable: {'Sí' if meta['playable_in_embed'] else 'No'}")
        if result.get("visual_description"):
            lines.append(f"👁️ Frame (miniatura): {result['visual_description'][:400]}")
        if jev_decision.get("status") == "ok":
            lines.append(f"🎯 Uso sugerido (JEV): {jev_decision.get('choice', '?')} "
                         f"(confianza: {jev_decision.get('score', '?')})")
        if result.get("video_accessible") is True:
            lines.append(f"✅ Video accesible (stream legible, {result.get('video_first_bytes',0)} B leídos)")
        elif result.get("video_accessible") is False:
            lines.append(f"⚠️ Video no accesible: {result.get('video_error','')[:100]}")
        else:
            lines.append("ℹ️ Sin URL directa del video")

        # Análisis de comentarios
        ca = meta.get("comments_analyzed", {})
        if ca.get("count", 0) > 0:
            lines.append(f"\n💬 Comentarios: {ca['count']} total, sentimiento {ca.get('sentiment','?')} "
                         f"(+{ca.get('positive_approx',0)} / -{ca.get('negative_approx',0)})")
            if ca.get("top_comments"):
                lines.append("   Top comentarios:")
                for tc in ca["top_comments"][:3]:
                    lines.append(f"     - {tc['author']}: {tc['text'][:100]} ({tc['likes']} ❤️)")
            if ca.get("themes"):
                lines.append("   Temas frecuentes: " + ", ".join(f"{t['word']}({t['count']})" for t in ca["themes"][:5]))

        # Compatibilidad
        comp = result.get("compatibilidad", {})
        if comp.get("integrable_en_aria"):
            lines.append(f"\n✅ Integrable en ARIA ({len(comp['integrable_en_aria'])}):")
            for item in comp["integrable_en_aria"]:
                lines.append(f"   • {item}")
        if comp.get("ideas_de_plataformas_incompatibles"):
            lines.append(f"\n💡 Ideas de plataformas incompatibles ({len(comp['ideas_de_plataformas_incompatibles'])}):")
            for item in comp["ideas_de_plataformas_incompatibles"]:
                lines.append(f"   • {item}")

        lines.append(f"💾 Informe: {report_file.name}")

        # ═════════════════════════════════════════════════════════════════════
        # 10. Integración en grafo de conocimiento de ARIA
        # ══════════════════════════════════════════════════════════════════════
        if self._kg:
            try:
                media_id = f"MEDIA-{meta.get('id', 'unknown')}"
                host_label = meta.get("extractor", host) or host
                autor = meta.get("author", "Desconocido")
                autor_id = f"AUTOR-{autor.replace(' ', '_')}"

                self._kg.add_node(media_id, meta.get("title", "Sin título"), "media", {
                    "url": url,
                    "host": host_label,
                    "author": autor,
                    "duration": meta.get("duration", 0),
                    "views": meta.get("view_count", 0),
                    "likes": meta.get("like_count", 0),
                    "upload_date": meta.get("upload_date", ""),
                    "extractor": meta.get("extractor", ""),
                    "jev_choice": jev_decision.get("choice", "") if jev_decision.get("status") == "ok" else "",
                    "jev_score": jev_decision.get("score", "") if jev_decision.get("status") == "ok" else "",
                })
                self._kg.add_node(autor_id, autor, "autor", {
                    "uploader_id": meta.get("uploader_id", ""),
                    "channel_followers": meta.get("channel_follower_count", 0),
                })
                self._kg.add_edge(autor_id, media_id, "crea", weight=0.9)

                # Nodos de temas/categorías
                for cat in (meta.get("categories") or [])[:5]:
                    cat_id = f"CAT-{cat.replace(' ', '_')}"
                    self._kg.add_node(cat_id, cat, "categoria", {})
                    self._kg.add_edge(media_id, cat_id, "pertenece_a", weight=0.7)

                # Nodos de hashtags
                for tag in (meta.get("tags") or [])[:10]:
                    tag_id = f"TAG-{tag.replace(' ', '_')}"
                    self._kg.add_node(tag_id, tag, "hashtag", {})
                    self._kg.add_edge(media_id, tag_id, "tiene_tag", weight=0.6)

                # Nodo de plataforma
                plat_id = f"PLAT-{host_label.replace(' ', '_')}"
                self._kg.add_node(plat_id, host_label, "plataforma", {})
                self._kg.add_edge(media_id, plat_id, "publicado_en", weight=0.8)

                result["kg_integrated"] = True
                result["kg_nodes"] = [media_id, autor_id, plat_id]
            except Exception as exc:
                logger.debug(f"No se pudo integrar en grafo de conocimiento: {exc}")
                result["kg_integrated"] = False
                result["kg_error"] = str(exc)

        # Guardar ideas de plataformas incompatibles en el archivo de ideas creativas
        comp = result.get("compatibilidad", {})
        ideas_incomp = comp.get("ideas_de_plataformas_incompatibles", [])
        if ideas_incomp:
            try:
                self._save_ideas(ideas_incomp)
            except Exception:
                pass

        result["summary"] = "\n".join(lines)
        return result


    def _describe_image_with_ollama(self, image_path: str) -> str:
        """Describe una imagen usando Ollama vision (granite3.2-vision:2b)."""
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from scripts.aria_eyes import OllamaVision, load_source
            client = OllamaVision(max_side=512, num_ctx=4096)
            sources = load_source(Path(image_path), 1)
            if not sources:
                return "No se pudo cargar la imagen para visión."
            label, img = sources[0]
            prompt = ("Describe detalladamente en español qué se ve en esta imagen: "
                      "personas, objetos, texto visible, acciones, entorno, colores, estilo, "
                      "cualquier detalle relevante para clasificar el contenido. Sé conciso pero completo.")
            return client.complete(prompt, [img])
        except Exception as exc:
            logger.warning(f"Ollama vision falló: {exc}")
            return f"Visión no disponible: {exc}"

    def _jev_classify_usage(self, meta: Dict[str, Any], visual_desc: str) -> Dict[str, Any]:
        """Clasifica el tipo de uso del contenido con JEV (decisión tipada).

        JEV devuelve una choice (tipo de contenido) y un score (confianza).
        Si no hay API de JEV disponible, usa fallback local con Ollama chat.
        """
        jev_api_key = os.getenv("JEV_API_KEY", "")
        jev_url = os.getenv("JEV_API_URL", "https://api.jevtypesafeai.com/v1/systemone")

        state = {
            "platform": "instagram",
            "title": meta.get("title", ""),
            "description": meta.get("description", ""),
            "visual_description": visual_desc,
            "og_type": meta.get("type", ""),
        }
        questions = [
            {"id": "uso", "type": "choice",
             "options": ["educativo", "tutorial", "entretenimiento", "referencia", "inspiracion", "otro"],
             "question": "¿Cuál es el tipo de uso principal de este contenido?"},
            {"id": "valor", "type": "score",
             "question": "¿Qué tan valioso es este contenido para archivar y reusar? (0-100)"},
        ]

        if jev_api_key and jev_url:
            try:
                import urllib.request
                payload = json.dumps({"state": state, "questions": questions}).encode("utf-8")
                req = urllib.request.Request(
                    jev_url,
                    data=payload,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {jev_api_key}"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read())
                return {"status": "ok", "provider": "jev_api", "data": data}
            except Exception as exc:
                logger.warning(f"JEV API falló, usando fallback local: {exc}")

        # Fallback local: Ollama chat con decisión estructurada
        try:
            ctx = (f"Título: {state['title']}\n"
                   f"Descripción: {state['description']}\n"
                   f"Visual: {state['visual_description']}\n"
                   f"Tipo OG: {state['og_type']}\n")
            resp = self.ai.chat(
                message=("Clasifica este contenido de Instagram en UNA de estas categorías: "
                         "educativo, tutorial, entretenimiento, referencia, inspiracion, otro. "
                         "Además dale una puntuación de valor 0-100. "
                         "Responde SOLO en este formato: CATEGORIA|PUNTUACION\n"
                         f"{ctx}"),
                temperature=0.3,
                max_tokens=64,
            )
            text = resp.get("response", "").strip()
            choice, score = self._parse_jev_fallback(text, ctx)
            return {"status": "ok", "provider": "ollama_fallback",
                    "choice": choice, "score": score, "raw": text}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def _parse_jev_fallback(self, text: str, ctx: str) -> tuple[str, str]:
        """Extrae (choice, score) de la respuesta libre de Ollama, robusto a variaciones."""
        import re as _re
        # 1. Intento CATEGORIA|PUNTUACION
        m = _re.search(r"([A-Za-záéíóúñ ]+)\s*\|\s*(\d{1,3})", text)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        # 2. Intento "Categoría: X / Puntuación: Y" u otros separadores
        m = _re.search(r"(?:categor[ií]a|uso)\s*[:=]\s*([A-Za-záéíóúñ ]+)", text, _re.I)
        if m:
            cat = m.group(1).strip()
            m2 = _re.search(r"(?:puntuaci[óo]n|valor|score)\s*[:=]\s*(\d{1,3})", text, _re.I)
            return cat, m2.group(1).strip() if m2 else "50"
        # 3. Intento extraer la primera palabra reconocida entre opciones válidas
        valid = ["educativo", "tutorial", "entretenimiento", "referencia", "inspiracion", "otro"]
        low = text.lower()
        for opt in valid:
            if opt in low:
                m2 = _re.search(r"(\d{1,3})", text)
                return opt, m2.group(1) if m2 else "50"
        # 4. Último recurso: "otro"
        return "otro", "50"

    def _analyze_comments(self, comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analiza comentarios: conteo, sentimentos aproximados, temas, top por likes."""
        if not comments:
            return {"count": 0, "top_comments": [], "themes": [], "sentiment": "desconocido"}
        sorted_comments = sorted(comments, key=lambda c: c.get("like_count", 0), reverse=True)
        top = sorted_comments[:10]
        # Temas simples: palabras frecuentes en los textos
        word_freq: Dict[str, int] = {}
        for c in comments:
            text = c.get("text", "").lower()
            for word in text.split():
                w = word.strip(".,!?¿¡()[]\"'#@:;")
                if len(w) > 3:
                    word_freq[w] = word_freq.get(w, 0) + 1
        themes = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        # Sentimiento muy aproximado por emojis/palabras clave
        pos = sum(1 for c in comments if any(e in c.get("text", "") for e in ["🙌","❤️","🔥","👍","😍","✨","💯","👏","❤","love","great","nice","good","amazing","best"]))
        neg = sum(1 for c in comments if any(e in c.get("text", "") for e in ["👎","😡","😠","💩","hate","bad","worst","terrible","awful"]))
        total = len(comments)
        sentiment = "positivo" if pos > neg * 1.5 else ("negativo" if neg > pos * 1.5 else "neutral")
        return {
            "count": total,
            "positive_approx": pos,
            "negative_approx": neg,
            "sentiment": sentiment,
            "top_comments": [{"author": c.get("author", ""), "text": c.get("text", "")[:200],
                             "likes": c.get("like_count", 0)} for c in top],
            "themes": [{"word": w, "count": cnt} for w, cnt in themes],
        }

    def _extract_json_ld(self, html: str) -> List[Dict[str, Any]]:
        """Extrae datos JSON-LD estructurados del HTML."""
        import json as _json
        results: List[Dict[str, Any]] = []
        for m in _re.finditer(r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, _re.S | _re.I):
            try:
                data = _json.loads(m.group(1).strip())
                if isinstance(data, list):
                    results.extend(data)
                else:
                    results.append(data)
            except Exception:
                continue
        return results

    def _analyze_compatibility(self, meta: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """Analiza qué información es integrable en ARIA y qué ideas sacar de plataformas incompatibles."""
        host = (result.get("host", "") or "").lower()
        ytdlp_ok = not result.get("ytdlp_meta_error")
        video_accessible = result.get("video_accessible")
        has_thumb = bool(result.get("thumbnail"))
        has_visual = bool(result.get("visual_description")) and "no disponible" not in result.get("visual_description", "").lower()
        has_video_url = bool(meta.get("video_url"))

        integrable = []
        ideas_incompatible = []

        # Qué se puede integrar en ARIA (disponible ahora)
        if ytdlp_ok:
            integrable.append("Metadatos completos de yt-dlp (título, autor, descripción, duración, vistas, likes, fecha)")
        if has_thumb:
            integrable.append("Miniatura descargable para visión local")
        if has_visual:
            integrable.append("Descripción visual vía Ollama (granite3.2-vision:2b)")
        if video_accessible is True:
            integrable.append("Acceso al stream de video (Range request, sin descarga completa)")
        if meta.get("chapters"):
            integrable.append("Capítulos/segmentos del video para navegación por tiempo")
        if meta.get("subtitle_languages") or meta.get("auto_caption_languages"):
            integrable.append("Idiomas de subtítulos disponibles para transcripción futura")
        if meta.get("comments_analyzed", {}).get("count", 0) > 0:
            integrable.append("Análisis de comentarios (sentimiento, temas, top comentarios)")
        if meta.get("json_ld"):
            integrable.append("Datos JSON-LD estructurados de la página")

        # Qué ideas sacar de plataformas incompatibles (sin acceso directo)
        if not ytdlp_ok:
            ideas_incompatible.append("yt-dlp falló: usar oembed + scraping HTML como fallback (título, autor, imagen, tipo OG)")
        if video_accessible is not True:
            ideas_incompatible.append("Sin URL directa de video: usar solo miniatura + clasificación JEV + metadatos públicos")
        if not has_thumb:
            ideas_incompatible.append("Sin miniatura: clasificación basada solo en texto (título/descripción) y OG tags")
        if host and "tiktok" in host:
            ideas_incompatible.append("TikTok: extraer sonidos/música, hashtags, efectos, desafíos, duets, stitches como categorías de contenido")
        if host and "youtube" in host:
            ideas_incompatible.append("YouTube: extraer listas de reproducción, end screens, cards, miembros del canal, super chats")
        if host and "instagram" in host:
            ideas_incompatible.append("Instagram: extraer reels relacionados, stories destacadas, colaboradores, etiquetas de productos, lugares")
        if not meta.get("tags"):
            ideas_incompatible.append("Sin tags de yt-dlp: inferir categorías desde descripción y hashtags en el texto")

        return {
            "integrable_en_aria": integrable,
            "ideas_de_plataformas_incompatibles": ideas_incompatible,
            "compatibilidad_score": len(integrable) / max(len(integrable) + len(ideas_incompatible), 1),
        }

    def _extract_platform_extras(self, html: str, host: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae información específica de cada plataforma desde el HTML:
        hashtags, colaboradores, lugares, productos, sonidos, listas de reproducción,
        reels relacionados, stories, etc.
        """
        extras: Dict[str, Any] = {
            "hashtags": [],
            "mentions": [],
            "locations": [],
            "products": [],
            "collaborators": [],
            "sounds": [],
            "related_reels": [],
            "playlists": [],
            "chapters_list": [],
        }
        import re as _re
        if not html:
            return extras

        # Hashtags desde el texto/descripción
        desc = meta.get("description", "") or ""
        tags_from_desc = _re.findall(r"#(\w+)", desc)
        extras["hashtags"].extend(tags_from_desc[:20])

        # Hashtags desde meta tags
        for m in _re.finditer(r'content=["\']([^"\']*#[^\s"\']+)["\']', html):
            for tag in _re.findall(r"#(\w+)", m.group(1)):
                if tag not in extras["hashtags"]:
                    extras["hashtags"].append(tag)
        extras["hashtags"] = extras["hashtags"][:30]

        # Menciones @usuario
        mentions = _re.findall(r"@(\w+)", desc)
        extras["mentions"] = list(dict.fromkeys(mentions))[:20]

        # ── Instagram específicos ──
        if "instagram" in host:
            # Colaboradores (co-author / invited)
            for m in _re.finditer(r'"username"\s*:\s*"([^"]+)"', html):
                u = m.group(1)
                if u not in extras["collaborators"]:
                    extras["collaborators"].append(u)
            extras["collaborators"] = extras["collaborators"][:10]

            # Lugar / location
            loc_m = _re.search(r'"location"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', html)
            if loc_m:
                extras["locations"].append(loc_m.group(1))

            # Productos etiquetados
            for m in _re.finditer(r'"product"\s*:\s*\{[^}]*"title"\s*:\s*"([^"]+)"', html):
                extras["products"].append(m.group(1))
            extras["products"] = extras["products"][:10]

            # Reels relacionados (shortcodes cercanos)
            for m in _re.finditer(r'/reel/([A-Za-z0-9_-]{11})/', html):
                short = m.group(1)
                if short not in extras["related_reels"]:
                    extras["related_reels"].append(short)
            extras["related_reels"] = extras["related_reels"][:10]

        # ── TikTok específicos ──
        if "tiktok" in host:
            # Sonido / música
            sound_m = _re.search(r'"music"\s*:\s*\{[^}]*"title"\s*:\s*"([^"]+)"', html)
            if sound_m:
                extras["sounds"].append(sound_m.group(1))
            artist_m = _re.search(r'"authorName"\s*:\s*"([^"]+)"', html)
            if artist_m:
                extras["sounds"].append(f"{artist_m.group(1)} - sonido")

            # Desafíos / efectos
            for m in _re.finditer(r'(?:challenge|effect)[^}]*(?:title|name)\s*:\s*"([^"]+)"', html, _re.I):
                val = m.group(1)
                if val:
                    extras["sounds"].append(val)
            extras["sounds"] = extras["sounds"][:10]

        # ── YouTube específicos ──
        if "youtube" in host or "youtu" in host:
            # Listas de reproducción
            for m in _re.finditer(r'"playlistId"\s*:\s*"([^"]+)"', html):
                pid = m.group(1)
                if pid not in extras["playlists"]:
                    extras["playlists"].append(pid)
            extras["playlists"] = extras["playlists"][:10]

            # Videos relacionados
            for m in _re.finditer(r'/watch\?v=([A-Za-z0-9_-]{11})', html):
                vid = m.group(1)
                if vid not in extras["related_reels"]:
                    extras["related_reels"].append(vid)
            extras["related_reels"] = extras["related_reels"][:10]

        return extras

    def _skill_media_related(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae contenido relacionado de la plataforma de un video/reel.

        Para Instagram: reels relacionados, colaboradores, lugares, productos.
        Para TikTok: sonidos, efectos, desafíos.
        Para YouTube: listas de reproducción, videos relacionados.
        """
        url = str(params.get("url", "")).strip()
        if not url:
            return {"status": "error", "error": "url requerida"}

        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()

        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/120.0 Safari/537.36")

        html = ""
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=25) as r:
                html = r.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            return {"status": "error", "error": f"no se pudo obtener HTML: {exc}"}

        meta: Dict[str, Any] = {}
        # Intentar obtener metadatos básicos de yt-dlp si está disponible
        try:
            import subprocess, json as _json, shutil, sys
            ytdlp_bin = shutil.which("yt-dlp") or shutil.which("youtube-dl")
            venv_yt_dlp = ARIA_APP.parent / ".venv" / "Scripts" / "yt-dlp.exe"
            ytdlp_cmd: List[str] = []
            if ytdlp_bin:
                ytdlp_cmd = [ytdlp_bin]
            elif venv_yt_dlp.exists():
                ytdlp_cmd = [str(venv_yt_dlp)]
            else:
                ytdlp_cmd = [sys.executable, "-m", "yt_dlp"]
            proc = subprocess.run(
                ytdlp_cmd + ["--dump-single-json", "--no-playlist", "--no-warnings",
                             "--skip-download", url],
                capture_output=True, text=True, timeout=60,
            )
            if proc.returncode == 0:
                ymeta = _json.loads(proc.stdout or "{}")
                meta["description"] = ymeta.get("description", "") or ""
                meta["tags"] = ymeta.get("tags", []) or []
        except Exception:
            pass

        extras = self._extract_platform_extras(html, host, meta)

        # Clasificar qué extras son integrables en ARIA
        integrable_related = []
        if extras["hashtags"]:
            integrable_related.append(f"Hashtags extraídos: {', '.join(extras['hashtags'][:10])}")
        if extras["collaborators"]:
            integrable_related.append(f"Colaboradores: {', '.join(extras['collaborators'][:5])}")
        if extras["locations"]:
            integrable_related.append(f"Lugares: {', '.join(extras['locations'][:5])}")
        if extras["products"]:
            integrable_related.append(f"Productos: {', '.join(extras['products'][:5])}")
        if extras["sounds"]:
            integrable_related.append(f"Sonidos/música: {', '.join(extras['sounds'][:5])}")
        if extras["related_reels"]:
            integrable_related.append(f"Contenido relacionado: {len(extras['related_reels'])} items")
        if extras["playlists"]:
            integrable_related.append(f"Listas de reproducción: {len(extras['playlists'])}")

        # Guardar ideas de plataformas incompatibles si no hay extras
        if not any(extras.values()):
            self._save_ideas([f"Plataforma {host}: sin extras extraíbles directamente; considerar scraping de API pública o feeds RSS"])

        return {
            "status": "ok",
            "skill": "media_related",
            "url": url,
            "host": host,
            "extras": extras,
            "integrable_en_aria": integrable_related,
            "summary": self._build_related_summary(extras, integrable_related),
        }

    def _build_related_summary(self, extras: Dict[str, Any], integrable: List[str]) -> str:
        lines = ["🔗 Contenido relacionado extraído:"]
        if extras["hashtags"]:
            lines.append(f"  🏷️ Hashtags: {', '.join(extras['hashtags'][:15])}")
        if extras["mentions"]:
            lines.append(f"  @ Menciones: {', '.join(extras['mentions'][:10])}")
        if extras["collaborators"]:
            lines.append(f"  🤝 Colaboradores: {', '.join(extras['collaborators'][:8])}")
        if extras["locations"]:
            lines.append(f"  📍 Lugares: {', '.join(extras['locations'][:8])}")
        if extras["products"]:
            lines.append(f"  🛍️ Productos: {', '.join(extras['products'][:8])}")
        if extras["sounds"]:
            lines.append(f"  🎵 Sonidos/música: {', '.join(extras['sounds'][:8])}")
        if extras["related_reels"]:
            lines.append(f"  📹 Relacionados: {', '.join(extras['related_reels'][:10])}")
        if extras["playlists"]:
            lines.append(f"  📋 Listas: {', '.join(extras['playlists'][:8])}")
        if integrable:
            lines.append("\n✅ Integrable en ARIA:")
            for item in integrable:
                lines.append(f"   • {item}")
        if not any(extras.values()):
            lines.append("  (no se extrajeron extras de esta plataforma)")
        return "\n".join(lines)

    # ─── Skill: Instagram RE (ingeniería inversa con REA) ───────────────────

    def _skill_instagram_re(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analiza Instagram.com con REA (ingeniería inversa de sitio web).

        Requiere Node.js + npx y el paquete rea-agents instalado.
        Ejecuta: npx rea-agents@latest analyze-website instagram.com --json
        """
        target = str(params.get("target", "instagram.com")).strip()
        import re as _re
        if not _re.match(r"^[\w\.\-]+$", target):
            return {"status": "error", "error": "target no válido"}

        npx = shutil.which("npx") or shutil.which("npx.ps1")
        if not npx:
            return {"status": "error", "error": "npx no encontrado; instala Node.js para usar REA"}

        try:
            proc = subprocess.run(
                [npx, "-y", "rea-agents@latest", "analyze-website", target, "--json"],
                capture_output=True, text=True, timeout=120,
            )
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            data = None
            if out:
                try:
                    data = json.loads(out)
                except json.JSONDecodeError:
                    data = {"raw": out[:2000]}
            return {
                "status": "ok" if proc.returncode == 0 else "error",
                "skill": "instagram_re",
                "target": target,
                "returncode": proc.returncode,
                "data": data,
                "stderr": err[-1000:] if err else "",
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "timeout analizando con REA (120s)"}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    # ═════════════════════════════════════════════════════════════════════════════
    # Skill: RAG — Retrieval-Augmented Generation
    # ═════════════════════════════════════════════════════════════════════════════

    def _skill_rag_retrieve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Recupera contexto relevante usando el motor RAG."""
        query = str(params.get("query", "")).strip()
        top_k = int(params.get("top_k", 5))
        if not query:
            return {"status": "error", "error": "query requerida"}
        result = self.rag.retrieve(query, top_k=top_k)
        return {
            "status": "ok",
            "skill": "rag_retrieve",
            "query": query,
            "hits": result["hits"],
            "context": result["context"],
            "total_hits": result["total_hits"],
        }

    def _skill_rag_add(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Agrega texto al sistema RAG."""
        content = str(params.get("content", "")).strip()
        source = str(params.get("source", "user"))
        if not content:
            return {"status": "error", "error": "content requerido"}
        result = self.rag.add_text(content, source=source)
        return {
            "status": "ok",
            "skill": "rag_add",
            "entry_id": result["entry_id"],
            "stm_entries": result["stm_entries"],
            "consolidated": result["consolidated"],
        }

    # ═════════════════════════════════════════════════════════════════════════════
    # Skill: Memoria (corto y largo plazo)
    # ═════════════════════════════════════════════════════════════════════════════

    def _skill_memory_add(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Agrega entrada a memoria."""
        role = str(params.get("role", "user"))
        content = str(params.get("content", "")).strip()
        importance = float(params.get("importance", 0.5))
        if not content:
            return {"status": "error", "error": "content requerido"}
        self.stm.add(role, content, importance=importance)
        return {"status": "ok", "skill": "memory_add", "role": role, "content": content[:100]}

    def _skill_memory_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Busca en memoria corto y largo plazo."""
        query = str(params.get("query", "")).strip()
        top_k = int(params.get("top_k", 5))
        if not query:
            return {"status": "error", "error": "query requerida"}
        stm_hits = self.stm.search(query, top_k=top_k)
        ltm_hits = self.ltm.search(query, top_k=top_k)
        vs_hits = self.vs.search(query, top_k=top_k)
        return {
            "status": "ok",
            "skill": "memory_search",
            "query": query,
            "short_term": stm_hits,
            "long_term": ltm_hits,
            "vector": vs_hits,
        }

    def _skill_memory_consolidate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Consolida memoria: promueve entradas importantes de corto a largo plazo."""
        result = self.memory_consolidator.consolidate()
        return {"status": "ok", "skill": "memory_consolidate", **result}

    def _skill_memory_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Estadísticas del sistema de memoria."""
        return {
            "status": "ok",
            "skill": "memory_stats",
            "short_term": self.stm.stats(),
            "long_term": self.ltm.get_stats(),
            "vector": self.vs.get_stats(),
            "consolidator": self.memory_consolidator.stats(),
        }

    # ═════════════════════════════════════════════════════════════════════════════
    # Skills: tres capas de memoria (Mnemosyne / Hindsight / Obsidian Wiki)
    # ═════════════════════════════════════════════════════════════════════════════

    def _skill_memory_layers(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Estado de las tres capas de memoria."""
        return {
            "status": "ok",
            "skill": "memory_layers",
            "mnemosyne": self.mnemosyne.stats(),
            "hindsight": self.hindsight.stats(),
            "obsidian_wiki": self.wiki.stats(),
            "capas": {
                "operativa": "Mnemosyne (buffer de sesion, zero-dependency)",
                "reflexion": "Hindsight (LLM: preferencias y patrones)",
                "mundo": "Obsidian Wiki (conocimiento permanente en Markdown)",
            },
        }

    def _skill_mnemosyne_add(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Guarda una entrada en Mnemosyne."""
        content = str(params.get("content", "")).strip()
        if not content:
            return {"status": "error", "skill": "mnemosyne_add", "error": "contenido vacio"}
        role = str(params.get("role", "user"))
        importance = float(params.get("importance", 0.5))
        tags = params.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        entry_id = self.mnemosyne.add(
            role=role, content=content, importance=importance, tags=tags)
        return {
            "status": "ok", "skill": "mnemosyne_add", "entry_id": entry_id,
            "role": role, "importance": importance, "stats": self.mnemosyne.stats(),
        }

    def _skill_mnemosyne_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Busca en Mnemosyne."""
        query = str(params.get("query", "")).strip()
        if not query:
            return {"status": "error", "skill": "mnemosyne_search", "error": "consulta vacia"}
        top_k = int(params.get("top_k", 5))
        return {
            "status": "ok", "skill": "mnemosyne_search", "query": query,
            "results": self.mnemosyne.search(query, top_k=top_k),
        }

    def _skill_hindsight_reflect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Reflexiona con LLM sobre una conversacion."""
        text = str(params.get("conversation", params.get("text", ""))).strip()
        if not text:
            return {"status": "error", "skill": "hindsight_reflect", "error": "conversacion vacia"}
        session_id = str(params.get("session_id", "")) or f"session_{int(time.time())}"
        reflection = self.hindsight.reflect_on_session(
            session_id=session_id,
            conversation_text=text,
            context_hints=params.get("context") or {},
        )
        return {
            "status": "ok", "skill": "hindsight_reflect",
            "reflection_id": reflection.reflection_id,
            "session_id": reflection.session_id,
            "summary": reflection.summary,
            "insights_found": reflection.insights_found,
            "preferences_learned": reflection.preferences_learned,
            "patterns_identified": reflection.patterns_identified,
        }

    def _skill_hindsight_insights(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Lista los insights aprendidos."""
        category = params.get("category")
        min_conf = float(params.get("min_confidence", 0.0))
        top_k = int(params.get("top_k", 20))
        insights = self.hindsight.get_insights(
            category=category, min_confidence=min_conf, top_k=top_k)
        return {
            "status": "ok", "skill": "hindsight_insights",
            "count": len(insights),
            "insights": [
                {
                    "insight_id": i.insight_id, "title": i.title,
                    "description": i.description, "category": i.category,
                    "confidence": round(i.confidence, 3),
                    "evidence_count": i.evidence_count,
                }
                for i in insights
            ],
        }

    def _skill_hindsight_context(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Contexto de Hindsight relevante para una consulta."""
        query = str(params.get("query", "")).strip()
        if not query:
            return {"status": "error", "skill": "hindsight_context", "error": "consulta vacia"}
        top_k = int(params.get("top_k", 5))
        return {
            "status": "ok", "skill": "hindsight_context", "query": query,
            "context": self.hindsight.get_context_for_query(query, top_k=top_k),
        }

    def _skill_wiki_write(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Escribe una nota permanente en el wiki."""
        title = str(params.get("title", "")).strip()
        content = str(params.get("content", ""))
        if not title:
            return {"status": "error", "skill": "wiki_write", "error": "titulo vacio"}
        tags = params.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        links = params.get("links") or []
        if isinstance(links, str):
            links = [l.strip() for l in links.split(",") if l.strip()]
        note_id = self.wiki.add_note(
            title=title, content=content, tags=tags, links=links,
            metadata=params.get("metadata") or {})
        return {
            "status": "ok", "skill": "wiki_write", "note_id": note_id,
            "path": str(self.wiki._note_path(note_id)),
        }

    def _skill_wiki_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Lee una nota del wiki."""
        ref = str(params.get("title", params.get("note_id", ""))).strip()
        if not ref:
            return {"status": "error", "skill": "wiki_read", "error": "titulo o note_id vacio"}
        note = self.wiki.get_note(ref) or self.wiki.get_note_by_title(ref)
        if not note:
            return {"status": "error", "skill": "wiki_read", "error": f"nota no encontrada: {ref}"}
        return {
            "status": "ok", "skill": "wiki_read",
            "note_id": note.note_id, "title": note.title, "content": note.content,
            "tags": note.tags, "links": note.links,
        }

    def _skill_wiki_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Busca notas en el wiki."""
        query = str(params.get("query", "")).strip()
        if not query:
            return {"status": "error", "skill": "wiki_search", "error": "consulta vacia"}
        top_k = int(params.get("top_k", 10))
        results = self.wiki.search(query, top_k=top_k)
        if not results:
            tag = str(params.get("tag", "")).strip()
            if tag:
                results = [
                    {"note_id": n.note_id, "title": n.title, "content": n.content[:500],
                     "tags": n.tags, "score": 1.0, "source": "obsidian_wiki"}
                    for n in self.wiki.get_by_tag(tag, top_k=top_k)
                ]
        return {"status": "ok", "skill": "wiki_search", "query": query, "results": results}

    # ═════════════════════════════════════════════════════════════════════════════
    # Skills: guard de procesos
    # ═════════════════════════════════════════════════════════════════════════════

    def _skill_process_guard_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Politica de terminacion de procesos."""
        return {
            "status": "ok",
            "skill": "process_guard_status",
            "policy": self.process_guard.describe(),
            "snapshot": self.process_guard.snapshot(),
        }

    def _skill_process_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Lista procesos con su veredicto frente al guard (no termina nada)."""
        try:
            import psutil
        except Exception as exc:
            return {"status": "error", "skill": "process_list", "error": f"psutil no disponible: {exc}"}
        limit = int(params.get("limit", 40))
        name_filter = str(params.get("name", "")).strip().lower()
        rows = []
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                name = (proc.info.get("name") or "").strip()
                if name_filter and name_filter not in name.lower():
                    continue
                verdict = self.process_guard.check(proc.info["pid"])
                rows.append({
                    "pid": proc.info["pid"],
                    "name": name,
                    "terminable": verdict.allowed,
                    "code": verdict.code,
                    "reason": verdict.reason,
                    "visible_window": verdict.visible_window,
                    "window_title": verdict.window_title,
                })
            except Exception:
                continue
        return {
            "status": "ok", "skill": "process_list",
            "count": len(rows), "processes": rows[:limit],
        }

    def _skill_process_terminate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Termina un PID explicito si el guard lo permite."""
        raw_pid = params.get("pid")
        if raw_pid in (None, ""):
            return {
                "status": "denied", "skill": "process_terminate",
                "terminated": False, "code": "pid_required",
                "reason": (
                    "Se requiere un PID explicito. Terminar por nombre esta prohibido "
                    "porque cerraria procesos del usuario que no se ven."
                ),
            }
        try:
            pid = int(raw_pid)
        except (TypeError, ValueError):
            return {"status": "denied", "skill": "process_terminate", "terminated": False,
                    "code": "invalid_pid", "reason": f"PID invalido: {raw_pid}"}
        result = self.process_guard.safe_terminate(
            pid, reason=str(params.get("reason", "solicitado por el usuario")))
        return {"status": result.get("status", "error"), "skill": "process_terminate", **result}

    # ═════════════════════════════════════════════════════════════════════════════
    # Skill: Modelos de IA
    # ═════════════════════════════════════════════════════════════════════════════

    def _skill_ai_models(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Lista modelos de IA disponibles."""
        return {
            "status": "ok",
            "skill": "ai_models",
            "models": self.ai_model_manager.list_models(),
            "stats": self.ai_model_manager.stats(),
        }

    def _skill_ai_train(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Inicia entrenamiento de IA asistente personal."""
        import asyncio
        method = str(params.get("method", "lora"))
        epochs = int(params.get("epochs", 3))
        lr = float(params.get("learning_rate", 5e-5))
        loop = asyncio.new_event_loop()
        job_id = loop.run_until_complete(
            self.ai_training_engine.start_training(
                method=method, epochs=epochs, learning_rate=lr,
            )
        )
        loop.close()
        return {
            "status": "ok",
            "skill": "ai_train",
            "job_id": job_id,
            "method": method,
        }

    def _skill_ai_train_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Consulta estado de un trabajo de entrenamiento."""
        job_id = str(params.get("job_id", ""))
        if not job_id:
            return {"status": "error", "error": "job_id requerido"}
        status = self.ai_training_engine.get_job_status(job_id)
        if not status:
            return {"status": "error", "error": "trabajo no encontrado"}
        return {"status": "ok", "skill": "ai_train_status", "job": status}

    def _skill_ai_improve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mejora reconocimiento de contenido (video, foto, cualquier formato)."""
        file_path = str(params.get("file_path", ""))
        url = str(params.get("url", ""))
        content_type = str(params.get("content_type", "auto"))

        if file_path:
            detected = self.ai_model_improver.detect_content_type(file_path)
        elif url:
            detected = self.ai_model_improver.detect_from_url(url)
        else:
            return {"status": "error", "error": "file_path o url requerido"}

        return {
            "status": "ok",
            "skill": "ai_improve",
            "content_type": detected,
            "supported_formats": self.ai_model_improver.stats(),
        }

    # ═════════════════════════════════════════════════════════════════════════════
    # Skill: Entornos especializados
    # ═════════════════════════════════════════════════════════════════════════════

    def _skill_env_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Lista entornos disponibles."""
        return {
            "status": "ok",
            "skill": "env_list",
            "environments": [
                {
                    "id": eid,
                    "name": env.name,
                    "description": env.description,
                    "active": env.active,
                }
                for eid, env in self.environments.items()
            ],
        }

    def _skill_env_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Inicia un entorno."""
        env_id = str(params.get("env_id", "")).strip()
        if not env_id:
            return {"status": "error", "error": "env_id requerido"}
        env = self.environments.get(env_id)
        if not env:
            return {"status": "error", "error": f"entorno no encontrado: {env_id}"}
        result = env.start()
        return {"status": "ok", "skill": "env_start", "environment": result}

    def _skill_env_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Detiene un entorno."""
        env_id = str(params.get("env_id", "")).strip()
        if not env_id:
            return {"status": "error", "error": "env_id requerido"}
        env = self.environments.get(env_id)
        if not env:
            return {"status": "error", "error": f"entorno no encontrado: {env_id}"}
        result = env.stop()
        return {"status": "ok", "skill": "env_stop", "environment": result}

    def _skill_env_process(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa una tarea dentro de un entorno."""
        env_id = str(params.get("env_id", "")).strip()
        task = params.get("task", {}) or {}
        if not env_id:
            return {"status": "error", "error": "env_id requerido"}
        env = self.environments.get(env_id)
        if not env:
            return {"status": "error", "error": f"entorno no encontrado: {env_id}"}
        result = env.process(task)
        return {"status": "ok", "skill": "env_process", "environment": env_id, "result": result}

    def _skill_env_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Estado de todos los entornos o uno específico."""
        env_id = params.get("env_id")
        if env_id:
            env = self.environments.get(str(env_id))
            if not env:
                return {"status": "error", "error": f"entorno no encontrado: {env_id}"}
            return {"status": "ok", "skill": "env_status", "environment": env.status()}
        return {
            "status": "ok",
            "skill": "env_status",
            "environments": {eid: env.status() for eid, env in self.environments.items()},
        }

    def _skill_drive_analyze(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Analiza Drive y archivos locales, extrayendo detalles clave y patrones."""
        result = self.continuous._analyze_drive_content()
        return {
            "status": result["status"],
            "skill": "drive_analyze",
            "desc": "Análisis de contenido Drive y archivos locales",
            "archivos": result["archivos"],
            "detalles_clave": result["detalles_clave"],
            "patrones": result["patrones"],
            "total_archivos": len(result["archivos"]),
        }

    def _handle_tool(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "ok", "tool": data.get("tool", ""),
                "output": "Herramienta ejecutada (modo nativo)", "time_ms": 0}

    def _skill_creative_ideas(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Genera ideas creativas basadas en conocimiento acumulado."""
        result = self.continuous._generate_creative_ideas()
        return {
            "status": result["status"],
            "skill": "creative_ideas",
            "desc": "Ideas creativas generadas por ARIA",
            "ideas": result["ideas"],
            "count": result["count"],
        }

    def _skill_auto_improve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-evaluación y propuestas de mejora del sistema."""
        result = self.continuous.auto_improve()
        return {
            "status": result["status"],
            "skill": "auto_improve",
            "desc": "Auto-mejora del sistema ARIA",
            "reporte": result.get("reporte", {}),
            "propuestas": result.get("propuestas", []),
        }

    def _skill_autonomo_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Inicia el motor de operación continua."""
        result = self.continuous.start()
        return {
            "status": result["status"],
            "skill": "autonomo_start",
            "desc": "Motor de operación continua",
            "message": result.get("message", ""),
            "running": self.continuous.status()["running"],
        }

    def _skill_autonomo_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Detiene el motor de operación continua."""
        result = self.continuous.stop()
        return {
            "status": result["status"],
            "skill": "autonomo_stop",
            "desc": "Motor de operación continua",
            "message": result.get("message", ""),
            "running": self.continuous.status()["running"],
        }

    def _handle_list_skills(self) -> Dict[str, Any]:
        return {"skills": [{"name": k, "desc": v["desc"], "category": v["category"]}
                           for k, v in self._skills.items()],
                "count": len(self._skills)}

    def _handle_status(self) -> Dict[str, Any]:
        return {"status": "ok", "uptime": round(time.time() - self.start_time, 1),
                "ai_provider": "ollama" if self.ai.is_available() else "local",
                "skills": len(self._skills), "mode": "native"}

    def _skill_sandbox_exec(self, params: Dict[str, Any]) -> Dict[str, Any]:
        code = str(params.get("code", "")).strip()
        if not code:
            return {"status": "error", "error": "codigo vacio"}
        timeout = int(params.get("timeout", 30))
        max_output = int(params.get("max_output_chars", 5000))
        allow_network = bool(params.get("allow_network", False))
        config = SandboxConfig(timeout=timeout, max_output_chars=max_output,
                               allow_network=allow_network,
                               allow_fs_write=bool(params.get("allow_fs_write", True)))
        result = self.sandbox.exec_code(code, config)
        return {"status": "ok" if result.ok else "error",
                "skill": "sandbox_exec", "sandbox_id": result.sandbox_id,
                "result": result.to_dict()}

    def _skill_sandbox_skill(self, params: Dict[str, Any]) -> Dict[str, Any]:
        skill_name = str(params.get("skill", "")).strip()
        if not skill_name:
            return {"status": "error", "error": "nombre de skill vacio"}
        skill_params = params.get("params", {}) or {}
        timeout = int(params.get("timeout", 30))
        max_output = int(params.get("max_output_chars", 5000))
        config = SandboxConfig(timeout=timeout, max_output_chars=max_output,
                               allow_network=False, allow_fs_write=False)
        result = self.sandbox.run_skill(skill_name, skill_params, config)
        return {"status": "ok" if result.ok else "error",
                "skill": "sandbox_skill", "sandbox_id": result.sandbox_id,
                "result": result.to_dict()}

    def _skill_sandbox_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_id = str(params.get("sandbox_id", "")).strip()
        if not sandbox_id:
            return {"status": "error", "error": "sandbox_id requerido"}
        st = self.sandbox.status(sandbox_id)
        if not st:
            return {"status": "error", "error": f"sandbox no encontrado: {sandbox_id}"}
        return {"status": "ok", "skill": "sandbox_status", "sandbox": st}

    def _skill_sandbox_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        sandbox_id = str(params.get("sandbox_id", "")).strip()
        if not sandbox_id:
            return {"status": "error", "error": "sandbox_id requerido"}
        stopped = self.sandbox.stop(sandbox_id)
        return {"status": "ok" if stopped else "error",
                "skill": "sandbox_stop", "stopped": stopped,
                "sandbox_id": sandbox_id}

    def _skill_sandbox_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        data = self.sandbox.list_all()
        return {"status": "ok", "skill": "sandbox_list", "data": data,
                "count": len(data.get("code", [])) + len(data.get("skills", []))}

    # ─── Handlers Discord ─────────────────────────────────────────────────────
    def _skill_discord_connect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        token = params.get("token") or self.discord_token
        if not token:
            return {"status": "error", "error": "DISCORD_BOT_TOKEN no configurado"}
        return discord_run({"action": "connect", "token": token})

    def _skill_discord_disconnect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return discord_run({"action": "disconnect"})

    def _skill_discord_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return discord_run({"action": "status"})

    def _skill_discord_guilds(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return discord_run({"action": "guilds"})

    def _skill_discord_channels(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return discord_run({"action": "channels", "guild_id": params.get("guild_id", 0)})

    def _skill_discord_send(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return discord_run({
            "action": "send",
            "channel_id": int(params.get("channel_id", 0)),
            "content": params.get("content", ""),
        })

    def _skill_discord_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return discord_run({
            "action": "read",
            "channel_id": int(params.get("channel_id", 0)),
            "limit": int(params.get("limit", 20)),
        })

    # ─── Handlers GitHub ──────────────────────────────────────────────────────
    def _skill_github_list_repos(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return github_run({"action": "list_repos", "user": params.get("user"),
                           "per_page": int(params.get("per_page", 50))})

    def _skill_github_search_repos(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return github_run({"action": "search_repos", "query": params.get("query", ""),
                           "per_page": int(params.get("per_page", 30))})

    def _skill_github_get_repo(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return github_run({"action": "get_repo", "full_name": params.get("full_name", "")})

    def _skill_github_file_content(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return github_run({"action": "file_content", "full_name": params.get("full_name", ""),
                           "path": params.get("path", ""), "ref": params.get("ref")})

    def _skill_github_list_dir(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return github_run({"action": "list_dir", "full_name": params.get("full_name", ""),
                           "path": params.get("path", ""), "ref": params.get("ref")})

    def _skill_github_issues(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return github_run({"action": "issues", "full_name": params.get("full_name", ""),
                           "state": params.get("state", "open")})

    def _skill_github_auth(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return github_run({"action": "auth"})

    # ─── Handlers Poder / Wake-on-LAN ─────────────────────────────────────────
    def _skill_power_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return power_run({"action": "status"})

    def _skill_power_wake_on_ac_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return power_run({"action": "can_wake_on_ac"})

    def _skill_wol_send(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return wol_run({
            "mac": params.get("mac", ""),
            "broadcast": params.get("broadcast", "255.255.255.255"),
            "port": int(params.get("port", 9)),
            "repeats": int(params.get("repeats", 3)),
        })

    # ─── Handlers Monitor de energia / WoL targets ──────────────────────────
    def _skill_power_monitor_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return power_monitor_run({"action": "start"})

    def _skill_power_monitor_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return power_monitor_run({"action": "stop"})

    def _skill_power_monitor_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return power_monitor_run({"action": "status"})

    def _skill_wol_add_target(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return power_monitor_run({"action": "add_target", "mac": params.get("mac", "")})

    def _skill_wol_remove_target(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return power_monitor_run({"action": "remove_target", "mac": params.get("mac", "")})

    def _skill_wol_list_targets(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return power_monitor_run({"action": "list_targets"})

    # ─── Handlers Web (buscar, clima, automatizacion) ──────────────────────
    def _skill_web_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return web_run({"domain": "search", "query": params.get("query", "")})

    def _skill_web_weather(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return web_run({"domain": "weather", "city": params.get("city", "Buenos Aires")})

    def _skill_web_automation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return web_run({
            "domain": "automation",
            "action": params.get("action", ""),
            "url": params.get("url", ""),
            "selector": params.get("selector", ""),
            "value": params.get("value", ""),
            "path": params.get("path", ""),
        })

    # ─── Handlers Files (listar, leer, escribir) ───────────────────────────
    def _skill_files_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return files_run({"domain": "list", "path": params.get("path", ".")})

    def _skill_files_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return files_run({"domain": "read", "path": params.get("path", "")})

    def _skill_files_write(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return files_run({
            "domain": "write",
            "path": params.get("path", ""),
            "content": params.get("content", ""),
        })

    # ─── Handlers Android (proyectos para Android Studio) ───────────────────
    def _skill_android_create_project(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({
            "domain": "project",
            "action": "create",
            "app_name": params.get("app_name", "MiApp"),
            "package": params.get("package", "com.aria.app"),
            "activity": params.get("activity", "MainActivity"),
            "min_sdk": params.get("min_sdk", "21"),
            "target_sdk": params.get("target_sdk", "34"),
            "compile_sdk": params.get("compile_sdk", "34"),
        })

    def _skill_android_build_apk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({
            "domain": "project",
            "action": "build_apk",
            "project": params.get("project", ""),
        })

    def _skill_android_list_projects(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({"domain": "project", "action": "list"})

    # ─── Handlers Android (proyectos completos para Android Studio) ─────────
    def _skill_android_project_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({"domain": "project", "action": "info", "project": params.get("project", "")})

    def _skill_android_add_activity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({
            "domain": "component", "action": "add_activity",
            "project": params.get("project", ""),
            "name": params.get("name", "SecondActivity"),
            "layout": params.get("layout", "activity_second"),
        })

    def _skill_android_add_fragment(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({
            "domain": "component", "action": "add_fragment",
            "project": params.get("project", ""),
            "name": params.get("name", "PlaceholderFragment"),
        })

    def _skill_android_add_viewmodel(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({
            "domain": "component", "action": "add_viewmodel",
            "project": params.get("project", ""),
            "name": params.get("name", "MainViewModel"),
        })

    def _skill_android_add_permission(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({
            "domain": "component", "action": "add_permission",
            "project": params.get("project", ""),
            "permission": params.get("permission", "android.permission.CAMERA"),
        })

    def _skill_android_add_dependency(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({
            "domain": "component", "action": "add_dependency",
            "project": params.get("project", ""),
            "dependency": params.get("dependency", ""),
        })

    def _skill_android_read_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({
            "domain": "project", "action": "read_file",
            "project": params.get("project", ""),
            "path": params.get("path", ""),
        })

    def _skill_android_write_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({
            "domain": "project", "action": "write_file",
            "project": params.get("project", ""),
            "path": params.get("path", ""),
            "content": params.get("content", ""),
        })

    def _skill_android_modify_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({
            "domain": "project", "action": "modify_file",
            "project": params.get("project", ""),
            "path": params.get("path", ""),
            "old": params.get("old", ""),
            "new": params.get("new", ""),
            "replace_all": bool(params.get("replace_all", False)),
        })

    def _skill_android_generate_gradle_wrapper(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({"domain": "project", "action": "generate_gradle_wrapper", "project": params.get("project", "")})

    def _skill_android_build_apk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({
            "domain": "project", "action": "build_apk",
            "project": params.get("project", ""),
            "variant": params.get("variant", "debug"),
        })

    def _skill_android_install_apk(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return android_run({
            "domain": "project", "action": "install_apk",
            "project": params.get("project", ""),
            "variant": params.get("variant", "debug"),
        })

    # ─── Handlers Media Extractor (video + web, sin descargar el video) ─────
    def _skill_adb_wireless(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from backend.skills.android.adb import run as adb_run
        return adb_run(params)

    def _skill_media_extract_video(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return media_extract_run({
            "action": "extract_video",
            "url": params.get("url", ""),
        })

    def _skill_media_extract_web(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return media_extract_run({
            "action": "extract_web",
            "url": params.get("url", ""),
        })

    def _skill_media_extract_transcript(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return media_extract_run({
            "action": "extract_transcript",
            "url": params.get("url", ""),
            "lang": params.get("lang"),
        })

    def _skill_media_extract_all(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return media_extract_run({
            "action": "extract_all",
            "url": params.get("url", ""),
            "lang": params.get("lang"),
        })

    # ─── Handlers Escritorio (bandeja + hotkeys globales) ─────────────────────
    def _skill_desktop_tray_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return desktop_run({"domain": "tray", "action": "start"})

    def _skill_desktop_tray_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return desktop_run({"domain": "tray", "action": "stop"})

    def _skill_desktop_tray_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return desktop_run({"domain": "tray", "action": "status"})

    def _skill_desktop_tray_notify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return desktop_run({
            "domain": "tray", "action": "notify",
            "title": params.get("title", "ARIA"),
            "message": params.get("message", ""),
        })

    def _skill_desktop_hotkey_register(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return desktop_run({
            "domain": "hotkeys", "action": "register",
            "combination": params.get("combination", ""),
            "callback": params.get("callback", ""),
        })

    def _skill_desktop_hotkey_unregister(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return desktop_run({
            "domain": "hotkeys", "action": "unregister",
            "combination": params.get("combination", ""),
        })

    def _skill_desktop_hotkey_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return desktop_run({"domain": "hotkeys", "action": "list"})

    def _skill_desktop_hotkey_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return desktop_run({"domain": "hotkeys", "action": "start"})

    def _skill_desktop_hotkey_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return desktop_run({"domain": "hotkeys", "action": "stop"})


# ─── Motor de Operación Continua y Auto-mejora ─────────────────────────────

class ContinuousEngine:
    """Motor de operación continua: analiza Drive, acumula conocimiento,
    genera ideas creativas y se auto-evalúa en bucle background."""

    def __init__(self, logic: NativeLogicEngine) -> None:
        self.logic = logic
        self.ai = logic.ai
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._interval = 300  # 5 min entre ciclos
        self._kg = None
        self._learning = None
        self._ideas_file = ARIA_APP / "data" / "creative_ideas.json"
        self._ideas_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_modules()

    def _load_modules(self) -> None:
        try:
            if str(PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT))
            from backend.learning.knowledge_graph import knowledge_graph as kg
            from backend.learning.learning_loop import learning_engine as le
            self._kg = kg
            self._learning = le
            logger.info("Módulos de aprendizaje cargados para operación continua")
        except Exception as exc:
            logger.warning(f"No se pudieron cargar módulos de aprendizaje: {exc}")

    def start(self) -> Dict[str, Any]:
        if self._running:
            return {"status": "ok", "message": "Ya está en ejecución"}
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return {"status": "ok", "message": "Motor continuo iniciado", "interval_s": self._interval}

    def stop(self) -> Dict[str, Any]:
        self._running = False
        return {"status": "ok", "message": "Motor continuo detenido"}

    def status(self) -> Dict[str, Any]:
        return {"running": self._running, "interval_s": self._interval}

    def _loop(self) -> None:
        logger.info("Bucle de operación continua iniciado")
        while self._running:
            try:
                self._cycle()
            except Exception as exc:
                logger.error(f"Error en ciclo continuo: {exc}")
            for _ in range(self._interval // 5):
                if not self._running:
                    break
                time.sleep(5)
        logger.info("Bucle de operación continua detenido")

    def _cycle(self) -> None:
        logger.info("Ciclo de operación continua: inicio")
        drive_result = self._analyze_drive_content()
        if self._kg and drive_result.get("status") == "ok":
            self._store_knowledge(drive_result)
        ideas = self._generate_creative_ideas()
        if self._learning:
            self._learning.evaluate_automation("continuous_cycle", {
                "success": True,
                "actions": ["drive_analyze", "knowledge_store", "creative_ideas"],
                "ideas_count": len(ideas.get("ideas", [])),
            })
        logger.info(f"Ciclo continuo completo: {ideas.get('count', 0)} ideas generadas")

    def _analyze_drive_content(self) -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "status": "ok",
            "archivos": [],
            "detalles_clave": [],
            "patrones": [],
            "timestamp": time.time(),
        }
        download_dir = PROJECT_ROOT / "downloads"
        if download_dir.exists():
            for f in sorted(download_dir.iterdir())[:20]:
                if f.is_file():
                    results["archivos"].append({
                        "nombre": f.name,
                        "ruta": str(f),
                        "tamano": f.stat().st_size,
                        "tipo": f.suffix.lower() or "sin_extension",
                    })
        desc_dir = PROJECT_ROOT / "instagram" / "descriptions"
        if desc_dir.exists():
            for f in sorted(desc_dir.glob("*.json"))[:20]:
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    nombre = f.stem
                    detalles = []
                    if isinstance(data, dict):
                        if "units" in data:
                            for unit in data["units"][:3]:
                                if "measured" in unit:
                                    detalles.append(f"{nombre}: {unit['measured']}")
                                if "ocr" in unit and unit["ocr"]:
                                    detalles.append(f"{nombre} OCR: {unit['ocr'][:100]}")
                        if "source" in data:
                            detalles.append(f"{nombre}: fuente={data['source']}")
                    results["detalles_clave"].extend(detalles[:5])
                    results["archivos"].append({
                        "nombre": nombre,
                        "ruta": str(f),
                        "tipo": ".json",
                        "origen": "drive_descripcion",
                    })
                except Exception:
                    pass
        tipos: Dict[str, int] = {}
        for a in results["archivos"]:
            t = a.get("tipo", "desconocido")
            tipos[t] = tipos.get(t, 0) + 1
        for t, c in sorted(tipos.items(), key=lambda x: -x[1]):
            results["patrones"].append(f"{c} archivo(s) de tipo {t}")
        return results

    def _store_knowledge(self, drive_result: Dict[str, Any]) -> None:
        if not self._kg:
            return
        ts = datetime.now().isoformat()
        node_id = f"DRIVE_SCAN-{int(time.time())}"
        self._kg.add_node(node_id, "Escaneo de Drive", "evento", {
            "timestamp": ts,
            "archivos": len(drive_result.get("archivos", [])),
            "detalles": len(drive_result.get("detalles_clave", [])),
        })
        for detalle in drive_result.get("detalles_clave", [])[:5]:
            detalle_id = f"DET-{int(time.time())}-{abs(hash(detalle)) % 10000}"
            self._kg.add_node(detalle_id, detalle[:100], "detalle", {"origen": "drive"})
            self._kg.add_edge(node_id, detalle_id, "contiene", weight=0.8)

    def _generate_creative_ideas(self) -> Dict[str, Any]:
        ideas: List[str] = []
        if self.ai.is_available():
            contexto = ""
            if self._kg:
                stats = self._kg.get_stats()
                contexto += f"Grafo: {stats['total_nodes']} nodos, {stats['total_edges']} conexiones. "
            prompt = (
                "Eres ARIA, una IA autónoma creativa. Basándote en el contexto "
                "del sistema (archivos analizados, grafo de conocimiento, detección de patrones), "
                "genera 5 ideas creativas y prácticas de qué se puede hacer con la información acumulada. "
                "Cada idea debe ser accionable, específica y original. Responde en español, "
                "una idea por línea, numeradas 1-5.\n\n"
                f"Contexto: {contexto}"
            )
            result = self.ai.chat(prompt, temperature=0.8, max_tokens=512)
            texto = result.get("response", "")
            for linea in texto.split("\n"):
                linea = linea.strip()
                if linea and (linea[0].isdigit() or "-" in linea[:3]):
                    ideas.append(linea)
        if not ideas:
            ideas = [
                "1. Crear un catálogo temático de los archivos de Drive por tipo y fecha.",
                "2. Generar un reporte semanal de patrones detectados en el contenido procesado.",
                "3. Proponer automatizaciones para organizar archivos según su contenido (OCR, metadatos).",
                "4. Usar el grafo de conocimiento para encontrar conexiones ocultas entre archivos.",
                "5. Diseñar un sistema de alertas cuando aparezcan archivos con patrones de seguridad relevantes.",
            ]
        self._save_ideas(ideas)
        return {"status": "ok", "ideas": ideas, "count": len(ideas), "timestamp": time.time()}

    def _save_ideas(self, ideas: List[str]) -> None:
        try:
            existentes: List[str] = []
            if self._ideas_file.exists():
                existentes = json.loads(self._ideas_file.read_text(encoding="utf-8"))
            existentes.extend(ideas)
            self._ideas_file.write_text(json.dumps(existentes[-100:], ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.debug(f"No se pudieron guardar ideas: {exc}")

    def get_ideas(self) -> Dict[str, Any]:
        try:
            if self._ideas_file.exists():
                ideas = json.loads(self._ideas_file.read_text(encoding="utf-8"))
                return {"status": "ok", "ideas": ideas, "count": len(ideas)}
        except Exception:
            pass
        return {"status": "ok", "ideas": [], "count": 0}

    def get_knowledge_stats(self) -> Dict[str, Any]:
        if self._kg:
            return {"status": "ok", **self._kg.get_stats()}
        return {"status": "error", "error": "grafo no disponible"}

    def auto_improve(self) -> Dict[str, Any]:
        if not self._learning:
            return {"status": "error", "error": "motor de aprendizaje no disponible"}
        report = self._learning.get_learning_report()
        proposals = self._learning.propose_improvements()
        return {
            "status": "ok",
            "reporte": report,
            "propuestas": [{"id": p.proposal_id, "titulo": p.title, "descripcion": p.description,
                           "impacto": p.impact, "esfuerzo": p.effort} for p in proposals],
        }


# ─── UI PyQt5 ───────────────────────────────────────────────────────────────


class NativeOrb:
    """Orb visual simple dibujado con QPainter (sin WebGL, sin Three.js)."""

    def __init__(self) -> None:
        self.state = "idle"  # idle, listening, talking, thinking, error
        self.scale = 1.0


class MainWindow:
    """Ventana principal de ARIA OS nativa (PyQt5)."""

    def __init__(self, logic: NativeLogicEngine) -> None:
        from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
        self.logic = logic
        self.ai = logic.ai

        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setStyle("Fusion")

        self.window = QMainWindow()
        self.window.setWindowTitle("ARIA OS v4.0 — Nativo")
        self.window.resize(1200, 800)
        self.window.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #060a13, stop:0.5 #0b1322, stop:1 #060a13
                );
            }
        """)

        central = QWidget()
        central.setAttribute(Qt.WA_TranslucentBackground, False)
        self.window.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Pozo de luz radial detrás del contenido (fondo visual)
        self._bg_glow = QLabel()
        self._bg_glow.setStyleSheet("""
            QLabel {
                background: qradialgradient(
                    cx:0.5, cy:0.3, radius:1.0,
                    stop:0 rgba(56, 189, 248, 0.10),
                    stop:0.4 rgba(14, 165, 233, 0.04),
                    stop:1 rgba(6, 10, 19, 0)
                );
            }
        """)
        self._bg_glow.setFixedSize(600, 600)
        self._bg_glow.lower()

        # Header
        header = QHBoxLayout()
        self.title = QLabel("ARIA OS")
        self.title.setStyleSheet("font-size: 28px; font-weight: bold; color: #38bdf8;")
        self.status_label = QLabel("● Nativo · Sin servidor · Sin puertos")
        self.status_label.setStyleSheet("color: #10b981; font-size: 14px;")
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.status_label)
        layout.addLayout(header)

        # Glow overlay detrás del orb (pulso visual)
        self._orb_glow = QLabel()
        self._orb_glow.setStyleSheet("""
            QLabel {
                background: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.5,
                    stop:0 rgba(56, 189, 248, 0.35),
                    stop:0.5 rgba(56, 189, 248, 0.12),
                    stop:1 rgba(6, 10, 19, 0)
                );
            }
        """)
        self._orb_glow.setFixedSize(340, 340)
        self._orb_glow.lower()

        # Orb (área visual central)
        self.orb_frame = QFrame()
        self.orb_frame.setFixedSize(220, 220)
        self.orb_frame.setStyleSheet("""
            QFrame {
                background: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.5,
                    stop:0 #38bdf8, stop:0.45 #0ea5e9, stop:0.7 #0f172a, stop:1 #050816
                );
                border-radius: 110px;
                border: 2px solid #38bdf8;
            }
        """)
        orb_shadow = QGraphicsDropShadowEffect()
        orb_shadow.setBlurRadius(30)
        orb_shadow.setColor(QColor(56, 189, 248, 120))
        orb_shadow.setOffset(0, 0)
        self.orb_frame.setGraphicsEffect(orb_shadow)
        self.orb_state = QLabel("IDLE")
        self.orb_state.setAlignment(Qt.AlignCenter)
        self.orb_state.setStyleSheet("color: #050816; font-weight: bold; font-size: 16px;")
        orb_layout = QVBoxLayout(self.orb_frame)
        orb_layout.addWidget(self.orb_state)
        layout.addWidget(self.orb_frame, alignment=Qt.AlignHCenter)

        # Chat
        chat_split = QHBoxLayout()

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("""
            QTextEdit {
                background: rgba(15, 23, 42, 0.75);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 12px;
                padding: 12px;
                color: #e2e8f0;
                font-size: 14px;
                selection-background-color: #38bdf8;
                selection-color: #050816;
            }
        """)
        chat_shadow = QGraphicsDropShadowEffect()
        chat_shadow.setBlurRadius(24)
        chat_shadow.setColor(QColor(6, 10, 19, 140))
        chat_shadow.setOffset(0, 4)
        self.chat_history.setGraphicsEffect(chat_shadow)
        self._append_system("ARIA OS nativo iniciado. Motor de lógica activo. IA: " +
                            ("Ollama (granite3.2-vision:2b)" if self.ai.is_available() else "modo local"))
        chat_split.addWidget(self.chat_history, stretch=3)

        side = QVBoxLayout()
        side.setSpacing(12)

        skills_label = QLabel("Habilidades")
        skills_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        side.addWidget(skills_label)

        self.skills_list = QListWidget()
        self.skills_list.setFixedWidth(220)
        self.skills_list.setStyleSheet("""
            QListWidget {
                background: rgba(15, 23, 42, 0.75);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 8px;
                color: #e2e8f0;
                font-size: 13px;
                padding: 4px;
            }
            QListWidget::item { padding: 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.06); border-radius: 6px; }
            QListWidget::item:selected { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #818cf8); color: #050816; }
        """)
        list_shadow = QGraphicsDropShadowEffect()
        list_shadow.setBlurRadius(18)
        list_shadow.setColor(QColor(6, 10, 19, 120))
        list_shadow.setOffset(0, 3)
        self.skills_list.setGraphicsEffect(list_shadow)
        self._refresh_skills()
        side.addWidget(self.skills_list)

        center_label = QLabel("Centro de Control")
        center_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold; margin-top: 12px;")
        side.addWidget(center_label)

        self.btn_status = QPushButton("Estado del Sistema")
        self.btn_status.setStyleSheet(self._btn_style())
        self.btn_status.clicked.connect(self._on_status)
        side.addWidget(self.btn_status)

        self.btn_skills = QPushButton("Listar Habilidades")
        self.btn_skills.setStyleSheet(self._btn_style())
        self.btn_skills.clicked.connect(self._on_list_skills)
        side.addWidget(self.btn_skills)

        self.btn_ping = QPushButton("Ping Interno")
        self.btn_ping.setStyleSheet(self._btn_style())
        self.btn_ping.clicked.connect(self._on_ping)
        side.addWidget(self.btn_ping)

        self.btn_autonomo = QPushButton("Modo Autónomo: OFF")
        self.btn_autonomo.setStyleSheet(self._btn_style())
        self.btn_autonomo.clicked.connect(self._on_autonomo_toggle)
        side.addWidget(self.btn_autonomo)

        self.btn_ideas = QPushButton("Ideas Creativas")
        self.btn_ideas.setStyleSheet(self._btn_style())
        self.btn_ideas.clicked.connect(self._on_ideas)
        side.addWidget(self.btn_ideas)

        self.btn_improve = QPushButton("Auto-mejora")
        self.btn_improve.setStyleSheet(self._btn_style())
        self.btn_improve.clicked.connect(self._on_auto_improve)
        side.addWidget(self.btn_improve)

        self.btn_knowledge = QPushButton("Conocimiento")
        self.btn_knowledge.setStyleSheet(self._btn_style())
        self.btn_knowledge.clicked.connect(self._on_knowledge)
        side.addWidget(self.btn_knowledge)

        self.btn_instagram_video = QPushButton("Instagram Video")
        self.btn_instagram_video.setStyleSheet(self._btn_style())
        self.btn_instagram_video.clicked.connect(self._on_instagram_video)
        side.addWidget(self.btn_instagram_video)

        self.btn_instagram_re = QPushButton("Instagram REA")
        self.btn_instagram_re.setStyleSheet(self._btn_style())
        self.btn_instagram_re.clicked.connect(self._on_instagram_re)
        side.addWidget(self.btn_instagram_re)

        side.addStretch()
        chat_split.addLayout(side, stretch=1)
        layout.addLayout(chat_split, stretch=1)

        # Input
        input_row = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Escribe a ARIA... (Ctrl+Enter para enviar)")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: rgba(15, 23, 42, 0.75);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 8px;
                padding: 12px 16px;
                color: #e2e8f0;
                font-size: 14px;
                selection-background-color: #38bdf8;
                selection-color: #050816;
            }
            QLineEdit:focus {
                border-color: #38bdf8;
                background: rgba(15, 23, 42, 0.90);
            }
        """)
        input_shadow = QGraphicsDropShadowEffect()
        input_shadow.setBlurRadius(16)
        input_shadow.setColor(QColor(6, 10, 19, 100))
        input_shadow.setOffset(0, 2)
        self.input_field.setGraphicsEffect(input_shadow)
        self.input_field.returnPressed.connect(self._on_send)
        input_row.addWidget(self.input_field)

        self.btn_send = QPushButton("Enviar")
        self.btn_send.setStyleSheet(self._btn_style(accent=True))
        self.btn_send.clicked.connect(self._on_send)
        input_row.addWidget(self.btn_send)

        layout.addLayout(input_row)

        # Atajo global: Ctrl+Shift+A para enfocar (simulado dentro de la app)
        self.shortcut = QShortcut(self.app.keyboardModifiers(), self.window)
        # Nota: el hotkey global real requiere pystray/keyboard; aquí usamos el foco de la ventana.

        self._chat_history: List[List[str]] = []

    def _btn_style(self, accent: bool = False) -> str:
        bg = "#38bdf8" if accent else "rgba(15, 23, 42, 0.75)"
        border = "#38bdf8" if accent else "rgba(255, 255, 255, 0.10)"
        return """
            QPushButton {
                background: %s;
                color: #e2e8f0;
                border: 1px solid %s;
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover {
                background: %s;
                border-color: #38bdf8;
            }
            QPushButton:pressed {
                padding-top: 11px;
                padding-bottom: 9px;
            }
        """ % (
            bg,
            border,
            "rgba(56, 189, 248, 0.15)" if accent else "rgba(15, 23, 42, 0.90)",
        )

    def _append_system(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.chat_history.append(f'<span style="color:#94a3b8">[{ts}] Sistema: {text}</span>')

    def _append_user(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.chat_history.append(f'<span style="color:#38bdf8">[{ts}] Tú: </span><span style="color:#e2e8f0">{text}</span>')

    def _append_aria(self, text: str, provider: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.chat_history.append(f'<span style="color:#c084fc">[{ts}] ARIA ({provider}): </span><span style="color:#e2e8f0">{text}</span>')

    def _refresh_skills(self) -> None:
        self.skills_list.clear()
        result = self.logic.process("list_skills", {})
        for s in result.get("skills", []):
            item = QListWidgetItem(f"• {s['name']} — {s['desc']}")
            self.skills_list.addItem(item)

    def _on_status(self) -> None:
        self._set_orb("thinking")
        result = self.logic.process("status", {})
        self._append_system(json.dumps(result, ensure_ascii=False, indent=2))
        self._set_orb("idle")

    def _on_list_skills(self) -> None:
        self._refresh_skills()
        self._append_system("Habilidades listadas.")

    def _on_ping(self) -> None:
        self._set_orb("listening")
        result = self.logic.process("ping", {})
        self._append_system(json.dumps(result, ensure_ascii=False))
        self._set_orb("idle")

    def _on_autonomo_toggle(self) -> None:
        self._set_orb("thinking")
        running = self.logic.continuous.status()["running"]
        if running:
            result = self.logic.process("skill", {"skill": "autonomo_stop", "params": {}})
            self.btn_autonomo.setText("Modo Autónomo: OFF")
            self.btn_autonomo.setStyleSheet(self._btn_style())
        else:
            result = self.logic.process("skill", {"skill": "autonomo_start", "params": {}})
            self.btn_autonomo.setText("Modo Autónomo: ON")
            self.btn_autonomo.setStyleSheet(self._btn_style(accent=True))
        self._append_system(json.dumps(result, ensure_ascii=False))
        self._set_orb("idle")

    def _on_ideas(self) -> None:
        self._set_orb("thinking")
        result = self.logic.process("skill", {"skill": "creative_ideas", "params": {}})
        self._append_system(json.dumps(result, ensure_ascii=False, indent=2))
        self._set_orb("idle")

    def _on_auto_improve(self) -> None:
        self._set_orb("thinking")
        result = self.logic.process("skill", {"skill": "auto_improve", "params": {}})
        self._append_system(json.dumps(result, ensure_ascii=False, indent=2))
        self._set_orb("idle")

    def _on_knowledge(self) -> None:
        self._set_orb("thinking")
        stats = self.logic.continuous.get_knowledge_stats()
        ideas = self.logic.continuous.get_ideas()
        texto = {
            "conocimiento": stats,
            "ideas_guardadas": ideas,
        }
        self._append_system(json.dumps(texto, ensure_ascii=False, indent=2))
        self._set_orb("idle")

    def _on_instagram_video(self) -> None:
        url, ok = QInputDialog.getText(
            self.window, "Instagram Video",
            "Pega la URL del reel/post de Instagram:",
        )
        if not ok or not url.strip():
            return
        self._set_orb("thinking")
        result = self.logic.process("skill", {
            "skill": "instagram_video",
            "params": {"url": url.strip()},
        })
        self._append_system(json.dumps(result, ensure_ascii=False, indent=2))
        self._set_orb("idle")

    def _on_instagram_re(self) -> None:
        target, ok = QInputDialog.getText(
            self.window, "Instagram REA",
            "Dominio a analizar (ej. instagram.com):",
            text="instagram.com",
        )
        if not ok or not target.strip():
            return
        self._set_orb("thinking")
        result = self.logic.process("skill", {
            "skill": "instagram_re",
            "params": {"target": target.strip()},
        })
        self._append_system(json.dumps(result, ensure_ascii=False, indent=2))
        self._set_orb("idle")

    def _on_send(self) -> None:
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self._append_user(text)
        self._set_orb("talking")

        def worker() -> None:
            result = self.logic.process("chat", {
                "message": text,
                "history": self._chat_history,
                "system_prompt": self.ai.system_prompt,
            })
            self._set_orb("idle")
            if result.get("status") == "ok":
                self._append_aria(result.get("response", ""), result.get("provider", "local"))
                self._chat_history.append([text, result.get("response", "")])
            else:
                self._append_system(f"Error: {result.get('error', 'desconocido')}")

        threading.Thread(target=worker, daemon=True).start()

    def _set_orb(self, state: str) -> None:
        colors = {
            "idle": "#38bdf8",
            "listening": "#c084fc",
            "talking": "#00d4ff",
            "thinking": "#f59e0b",
            "error": "#ef4444",
        }
        color = colors.get(state, "#38bdf8")
        self.orb_frame.setStyleSheet(f"""
            QFrame {{
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
                    stop:0 {color}, stop:0.4 #0ea5e9, stop:0.75 #0f172a, stop:1 #050816);
                border-radius: 110px;
                border: 2px solid {color};
            }}
        """)
        glow_shadow = QGraphicsDropShadowEffect()
        glow_shadow.setBlurRadius(40 if state != "idle" else 24)
        glow_shadow.setColor(QColor(int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16), 100))
        glow_shadow.setOffset(0, 0)
        self.orb_frame.setGraphicsEffect(glow_shadow)
        self.orb_state.setText(state.upper())
        self.orb_state.setStyleSheet(f"color: #050816; font-weight: bold; font-size: 16px;")

    def run(self) -> int:
        self.window.show()
        return self.app.exec()


# ─── Entry point ────────────────────────────────────────────────────────────


def main() -> int:
    print("[ARIA OS Native] Iniciando — sin HTTP, sin servidores, sin puertos", flush=True)

    ai = NativeAIProvider()
    logic = NativeLogicEngine(ai)

    ui = MainWindow(logic)
    logger.info("ARIA OS Native UI lista")
    return ui.run()


if __name__ == "__main__":
    sys.exit(main())
