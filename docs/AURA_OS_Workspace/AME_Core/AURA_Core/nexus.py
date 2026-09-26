import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("AURA_Nexus")


# ─────────────────────────────────────────────
# IMPORTACIONES DEFERIDAS (evitan ciclos)
# ─────────────────────────────────────────────
def _get_llm_router():
    from AURA_Core.automation.llm_router import llm_router

    return llm_router


def _get_knowledge_graph():
    from AURA_Core.memory.knowledge_graph import KnowledgeGraph

    return KnowledgeGraph()


def _get_event_manager():
    from AURA_Core.event_manager import EventManager

    return EventManager()


def _get_chronos():
    from AURA_Core.chronos import Chronos

    return Chronos()


def _get_rollercoin_healed():
    from AURA_Core.automation.rollercoin_healed import start_bot

    return start_bot


class AURANexus:
    """Singleton orquestador del ecosistema AURA."""

    _instance: Optional["AURANexus"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AURANexus":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_state()
            return cls._instance

    def _init_state(self) -> None:
        self._components: Dict[str, Any] = {}
        self.system_status: Dict[str, Any] = {
            "cpu": 0.0,
            "ame_battery": 0.0,
            "healer_status": "idle",
            "last_graph_relation": None,
            "active_threads": [],
            "mode": "local",
            "endpoint": "unknown",
            "uptime_start": time.time(),
            "critical_errors": [],
            "task_queue": {
                "current_task": None,
                "total_pending": 0,
                "total_running": 0,
                "total_completed": 0,
                "timestamp": time.time(),
            },
        }
        self._shutdown = threading.Event()
        self._watcher_thread: Optional[threading.Thread] = None

    @classmethod
    def get_instance(cls) -> "AURANexus":
        return cls()

    # ──────────────────────────────────────────
    # Ciclo de vida del sistema
    # ──────────────────────────────────────────

    def arrancar_sistema(self) -> Dict[str, Any]:
        logger.info("Arrancando AURA Nexus...")
        estado = {"ok": True, "pasos": {}}

        try:
            self._inicializar_llm_router()
            estado["pasos"]["llm_router"] = "ok"
        except Exception as exc:
            estado["pasos"]["llm_router"] = f"error: {exc}"
            estado["ok"] = False
            self._activar_modo_contingencia(str(exc))

        try:
            self._levantar_knowledge_graph()
            estado["pasos"]["knowledge_graph"] = "ok"
        except Exception as exc:
            estado["pasos"]["knowledge_graph"] = f"error: {exc}"
            estado["ok"] = False

        try:
            self._arrancar_event_manager()
            estado["pasos"]["event_manager"] = "ok"
        except Exception as exc:
            estado["pasos"]["event_manager"] = f"error: {exc}"
            estado["ok"] = False

        try:
            self._despertar_chronos()
            estado["pasos"]["chronos"] = "ok"
        except Exception as exc:
            estado["pasos"]["chronos"] = f"error: {exc}"
            estado["ok"] = False

        try:
            self._lanzar_bots_playwright()
            estado["pasos"]["rollercoin_healed"] = "ok"
        except Exception as exc:
            estado["pasos"]["rollercoin_healed"] = f"error: {exc}"
            estado["ok"] = False

        self._iniciar_watcher()
        logger.info("Estado de arranque: %s", estado)
        return estado

    def detener_sistema(self) -> None:
        logger.info("Deteniendo AURA Nexus...")
        self._shutdown.set()
        if self._watcher_thread and self._watcher_thread.is_alive():
            self._watcher_thread.join(timeout=5)
        for thread in list(self.system_status.get("active_threads", [])):
            if thread.is_alive():
                thread.join(timeout=10)
        logger.info("AURA Nexus detenido.")

    # ──────────────────────────────────────────
    # Inicialización por componentes
    # ──────────────────────────────────────────

    def _inicializar_llm_router(self) -> None:
        logger.info("Verificando LLMRouter...")
        try:
            from AURA_Core.neural.local_router import LocalRouter

            router = LocalRouter()
        except Exception as exc:
            raise RuntimeError(f"No se pudo cargar LocalRouter: {exc}") from exc
        try:
            import asyncio

            check = asyncio.run(router.chat("ping"))
            endpoint = getattr(router, "_lm_studio_base", "lm_studio")
            self.system_status["endpoint"] = endpoint
            self.system_status["mode"] = "local"
            logger.info("LLMRouter activo en %s", self.system_status["endpoint"])
        except Exception as exc:
            logger.warning("Fallo en LLMRouter primario: %s", exc)
            self.system_status["endpoint"] = "lm_studio"
            self.system_status["mode"] = "local"
            logger.info("Conmutado a endpoint local: lm_studio")

    def _levantar_knowledge_graph(self) -> None:
        kg = _get_knowledge_graph()
        kg._load()
        self._components["knowledge_graph"] = kg
        self.system_status["last_graph_relation"] = {}
        logger.info("KnowledgeGraph cargada.")

    def _arrancar_event_manager(self) -> None:
        try:
            em = _get_event_manager()
            if hasattr(em, "start"):
                em.start()
            self._components["event_manager"] = em
            logger.info("EventManager arrancado en puerto 8765.")
        except Exception as exc:
            logger.warning("EventManager no iniciado: %s", exc)

    def _despertar_chronos(self) -> None:
        try:
            chronos = _get_chronos()
            target = getattr(chronos, "run", None) or getattr(chronos, "start", None)
            if not target:
                raise AttributeError("Chronos sin método run/start")
            t = threading.Thread(target=target, daemon=True)
            t.start()
            self.system_status["active_threads"].append(t)
            logger.info("Chronos en segundo plano.")
        except Exception as exc:
            logger.warning("Chronos no iniciado: %s", exc)

    def _lanzar_bots_playwright(self) -> None:
        try:
            start_bot = _get_rollercoin_healed()
        except Exception as exc:
            logger.warning("Bot Playwright no disponible: %s", exc)
            return

        def _runner() -> None:
            while not self._shutdown.is_set():
                try:
                    start_bot()
                except Exception as exc:
                    logger.warning("Bot Playwright reiniciado por error: %s", exc)
                    time.sleep(5)

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        self.system_status["active_threads"].append(t)
        logger.info("Bots Playwright lanzados.")

    # ──────────────────────────────────────────
    # Watcher de salud del sistema
    # ──────────────────────────────────────────
    def _iniciar_watcher(self) -> None:
        def _watcher() -> None:
            while not self._shutdown.is_set():
                try:
                    self._chequear_salud_components()
                except Exception as exc:
                    logger.error("Error en watcher: %s", exc)
                time.sleep(30)

        self._watcher_thread = threading.Thread(target=_watcher, daemon=True)
        self._watcher_thread.start()
        logger.info("Watcher de salud iniciado.")

    def _chequear_salud_components(self) -> None:
        # Health check simple: si el LLMRouter está caído, reconectar
        llm_router = _get_llm_router()
        try:
            llm_router.chat(system_prompt="", user_prompt="ping", temperature=0.0, max_tokens=1)
            if self.system_status.get("mode") == "local":
                logger.info("Endpoint remoto recuperado, volviendo a modo normal.")
                self.system_status["mode"] = "remote"
                self.system_status["endpoint"] = llm_router.primary.name
        except Exception as exc:
            if self.system_status.get("mode") != "local":
                logger.warning("Endpoint primario caído: %s", exc)
                self._activar_modo_contingencia(str(exc))

    # ──────────────────────────────────────────
    # Gestión de excepciones y contingencia
    # ──────────────────────────────────────────

    def _activar_modo_contingencia(self, motivo: str) -> None:
        self.system_status["mode"] = "local"
        self.system_status.setdefault("critical_errors", []).append(
            {
                "timestamp": time.time(),
                "motivo": motivo,
                "endpoint": "lm_studio",
            }
        )
        self._broadcast_critical_error(
            tipo="system_critical_error",
            detalle=f"Conmutando a LM Studio local. Motivo: {motivo}",
        )

    def _broadcast_critical_error(self, tipo: str, detalle: str) -> None:
        payload = {"tipo": tipo, "detalle": detalle, "timestamp": time.time()}
        try:
            em = self._components.get("event_manager")
            if em:
                em.broadcast(payload)
        except Exception as exc:
            logger.error("No se pudo broadcastear error crítico: %s", exc)

    # ──────────────────────────────────────────
    # Telemetría y estado compartido
    # ──────────────────────────────────────────

    def actualizar_estado(self, datos: Dict[str, Any]) -> None:
        self.system_status.update(datos)

    def update_task_state(self, datos: Dict[str, Any]) -> None:
        """Actualiza el estado de la cola de tareas de JARVIS en el Nexus."""
        self.system_status["task_queue"] = datos
        logger.info(
            "[NEXUS] Estado de tareas actualizado: pending=%s running=%s completed=%s",
            datos.get("total_pending"),
            datos.get("total_running"),
            datos.get("total_completed"),
        )

    def obtener_estado(self) -> Dict[str, Any]:
        estado = dict(self.system_status)
        estado["uptime"] = time.time() - estado["uptime_start"]
        return estado


nexus = AURANexus()
