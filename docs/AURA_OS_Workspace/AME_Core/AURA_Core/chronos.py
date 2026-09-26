# AURA_Core/chronos.py
# Fase 20 - Ciclo de Vida Autónomo de Bucle Cerrado (modo simulación por defecto).
# Ejecuta rutinas de inspección, análisis de mercado, estrategia de bots y genera briefing matutino.

import json
import os
import time
import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from AURA_Core.dream_and_distill import run_dream, run_distill
except Exception:
    run_dream = None  # type: ignore
    run_distill = None  # type: ignore

from AURA_Core.core.task_manager import TaskManager, ChronosTaskInjector

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
except Exception:
    BackgroundScheduler = None  # type: ignore
    CronTrigger = None  # type: ignore


class Chronos:
    def __init__(self, simulate: bool = True) -> None:
        self.simulate = simulate
        self.logger = logging.getLogger("Chronos")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            self.logger.addHandler(handler)

        self.briefing_path = "AURA_Core/state_of_the_empire.md"
        self.scheduler: Optional[Any] = None
        self.ws_clients: List[Any] = []
        self.task_manager: Optional[TaskManager] = None
        self.task_injector: Optional[ChronosTaskInjector] = None

    def start(self) -> None:
        if BackgroundScheduler is None:
            self.logger.warning("apscheduler no disponible; usando bucle manual.")
            self._run_manual_loop()
            return

        # Integración con TaskManager y Nexus
        try:
            from AURA_Core.nexus import nexus

            self.task_manager = TaskManager(nexus_ref=nexus)
            self.task_injector = ChronosTaskInjector(self.task_manager)
            self.logger.info("[CHRONOS] TaskManager integrado con Nexus.")
        except Exception as e:
            self.logger.warning(f"[CHRONOS] No se pudo integrar TaskManager: {e}")
        self.scheduler = BackgroundScheduler()
        # Inspección autónoma cada 60 minutos
        self.scheduler.add_job(self.autonomous_inspection, CronTrigger(minute="0"))
        # Briefing matutino a las 07:00
        self.scheduler.add_job(self.morning_briefing, CronTrigger(hour=7, minute=0))
        # DREAM: Consolidación de memoria en reposo cada 30 minutos (detecta inactividad internamente)
        self.scheduler.add_job(self._run_dream_cycle, CronTrigger(minute="*/30"))
        # DISTILL: Análisis de patrones y creación de macros cada 60 minutos
        self.scheduler.add_job(self._run_distill_cycle, CronTrigger(minute="0"))
        self.scheduler.start()
        self.logger.info(
            "Chronos iniciado. Ciclos activos: inspección cada 60m, briefing diario 07:00, "
            "Dream cada 30m, Distill cada 60m."
        )

    def stop(self) -> None:
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            self.logger.info("Chronos detenido.")

    def _run_manual_loop(self) -> None:
        try:
            while True:
                self.autonomous_inspection()
                time.sleep(60 * 60)
        except KeyboardInterrupt:
            self.logger.info("Chronos detenido manualmente.")

    def autonomous_inspection(self) -> Dict[str, Any]:
        self.logger.info("Iniciando inspección autónoma...")
        report: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "ecosystem_health": self._step_ecosystem_health(),
            "market_analysis": self._step_market_analysis(),
            "bot_strategy": self._step_bot_strategy(),
            "anomalies": [],
        }
        # Consolidar anomalías detectadas
        eco_anomalies = report["ecosystem_health"].get("anomalies", [])
        if eco_anomalies:
            report["anomalies"].append({"type": "ecosystem_node_down", "nodes": eco_anomalies})
        if report["bot_strategy"].get("auto_heal_triggered"):
            report["anomalies"].append(
                {"type": "bot_strategy_idle", "metrics": report["bot_strategy"].get("metrics")}
            )
        # FASE 28: Disparar evento al motor de reglas IoT si hay anomalías
        if report["anomalies"]:
            self._dispatch_iot_event(report["anomalies"])
        self._persist_last_report(report)
        self.logger.info("Inspección autónoma completada.")
        return report

    def _step_ecosystem_health(self) -> Dict[str, Any]:
        nodes = ["Search Node", "HF Space", "JARVIS HUD"]
        statuses: Dict[str, str] = {}
        for node in nodes:
            if self.simulate:
                statuses[node] = "online"
            else:
                try:
                    import requests

                    # Placeholder: ping HTTP/WebSocket del nodo
                    r = requests.get(
                        f"http://{node.replace(' ', '-').lower()}.local:8080/health", timeout=5
                    )
                    statuses[node] = "online" if r.ok else "degraded"
                except Exception as e:
                    statuses[node] = f"error: {e}"
        anomalies = [node for node, st in statuses.items() if st != "online"]
        return {
            "nodes": statuses,
            "summary": ("Todos los nodos operativos" if not anomalies else "Requiere atención"),
            "anomalies": anomalies,
        }

    def _step_market_analysis(self) -> Dict[str, Any]:
        topics = ["desarrollo de software", "inteligencia artificial"]
        threads: List[Dict[str, str]] = []
        if self.simulate:
            threads = [
                {
                    "title": "Tendencias AI 2026",
                    "source": "Reddit",
                    "url": "https://reddit.com/ai2026",
                },
                {
                    "title": "Nuevas APIs de modelos locales",
                    "source": "Noticias",
                    "url": "https://news.local/apis",
                },
                {
                    "title": "Optimización de pipelines LLM",
                    "source": "Reddit",
                    "url": "https://reddit.com/llm",
                },
            ]
        else:
            try:
                import requests

                for topic in topics:
                    resp = requests.get(
                        "https://api.reddit.com/search", params={"q": topic, "limit": 3}, timeout=10
                    )
                    if resp.ok:
                        data = resp.json()
                        for item in data.get("data", {}).get("children", [])[:3]:
                            threads.append(
                                {
                                    "title": item.get("data", {}).get("title"),
                                    "source": "Reddit",
                                    "url": f"https://reddit.com{item.get('data', {}).get('permalink', '')}",
                                }
                            )
            except Exception as e:
                self.logger.error(f"Error en análisis de mercado: {e}")
        return {"topics": topics, "top_threads": threads[:3]}

    def _step_bot_strategy(self) -> Dict[str, Any]:
        status = "running" if self.simulate else "checking"
        metrics = {"hashrate": "0.0 H/s", "uptime": "0h", "tasks": 0}
        if self.simulate:
            metrics = {"hashrate": "125.4 H/s", "uptime": "4h", "tasks": 12}
        else:
            try:
                import requests

                r = requests.get("http://rollercoin.local:9090/status", timeout=5)
                if r.ok:
                    metrics = r.json()
            except Exception as e:
                self.logger.error(f"Error en bot strategy: {e}")
                status = "error"
        auto_heal = status == "running" and metrics.get("tasks", 0) == 0
        return {"status": status, "metrics": metrics, "auto_heal_triggered": auto_heal}

    def morning_briefing(self) -> Dict[str, Any]:
        report = self.autonomous_inspection()
        briefing = self._compile_briefing(report)
        self._save_briefing(briefing)
        self._broadcast_ws("morning_briefing", briefing)
        self.logger.info("Morning Briefing generado y difundido por WebSocket.")
        return briefing

    def _compile_briefing(self, report: Dict[str, Any]) -> str:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"# State of the Empire - {now}",
            "",
            "## Salud del Ecosistema",
            f"- Estado: {report['ecosystem_health']['summary']}",
        ]
        for node, st in report["ecosystem_health"]["nodes"].items():
            lines.append(f"- {node}: {st}")
        lines.extend(
            [
                "",
                "## Análisis del Mercado",
                f"- Temas: {', '.join(report['market_analysis']['topics'])}",
            ]
        )
        for idx, thread in enumerate(report["market_analysis"]["top_threads"], 1):
            lines.append(f"{idx}. [{thread['source']}] {thread['title']} ({thread['url']})")
        lines.extend(
            [
                "",
                "## Estrategia de Bots",
                f"- Estado: {report['bot_strategy']['status']}",
                f"- Métricas: {report['bot_strategy']['metrics']}",
                f"- Auto-reparación: {'Activada' if report['bot_strategy']['auto_heal_triggered'] else 'No necesaria'}",
                "",
                "---",
                "Generado automáticamente por Chronos.",
            ]
        )
        return "\n".join(lines)

    def _save_briefing(self, content: str) -> None:
        os.makedirs(os.path.dirname(self.briefing_path) or ".", exist_ok=True)
        with open(self.briefing_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _persist_last_report(self, report: Dict[str, Any]) -> None:
        path = "AURA_Core/latest_report.json"
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    def _run_dream_cycle(self) -> None:
        """Ejecuta ciclo DREAM si el usuario está inactivo >30 min."""
        if run_dream is None:
            self.logger.debug("[DREAM] Módulo no disponible, saltando.")
            return
        try:
            result = run_dream()
            if result.get("status") == "skipped":
                self.logger.info("[DREAM] Usuario activo, se omite consolidación.")
            else:
                self.logger.info(
                    f"[DREAM] Consolidación ejecutada: "
                    f"{result.get('removed_orphans',0)} nodos huérfanos eliminados, "
                    f"{result.get('compressed_chats',0)} chats comprimidos."
                )
        except Exception as e:
            self.logger.error(f"[DREAM] Error en ciclo: {e}")

    def _run_distill_cycle(self) -> None:
        """Ejecuta ciclo DISTILL: analiza patrones y genera skills."""
        if run_distill is None:
            self.logger.debug("[DISTILL] Módulo no disponible, saltando.")
            return
        try:
            result = run_distill()
            if result.get("new_skills", 0) > 0:
                for skill in result.get("skills", []):
                    if skill.get("steps"):
                        name = skill.get("name", "desconocida")
                        steps = ", ".join(skill["steps"][:3])
                        self.logger.info(
                            f"[DISTILL] Nueva macro sintetizada: '{name}' -> {steps}..."
                        )
                self._broadcast_ws(
                    "new_macro",
                    {
                        "message": (
                            f"💡 He detectado un patrón repetitivo y he sintetizado "
                            f"{result['new_skills']} macros. ¿Deseas ejecutarlas "
                            f"con un solo comando?"
                        ),
                        "skills": result.get("skills", []),
                    },
                )
        except Exception as e:
            self.logger.error(f"[DISTILL] Error en ciclo: {e}")

    def _dispatch_iot_event(self, anomalies: list) -> None:
        """Envía anomalías detectadas al EventManager para acciones IoT."""
        try:
            from AURA_Core.event_manager import EventManager

            em = EventManager(config={})
            em.broadcast(
                {
                    "tipo": "chronos_security_anomaly",
                    "anomalies": anomalies,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        except Exception as exc:
            self.logger.error(f"Error despachando evento IoT desde Chronos: {exc}")

    def register_ws(self, client: Any) -> None:
        self.ws_clients.append(client)

    def _broadcast_ws(self, event: str, payload: Any) -> None:
        # Reenvío a clientes WS locales registrados (ej. EventManager)
        for client in list(self.ws_clients):
            try:
                if hasattr(client, "send"):
                    client.send(json.dumps({"event": event, "payload": payload}))
            except Exception as e:
                self.logger.error(f"Error enviando WebSocket local: {e}")
        # Transmisión real al EventBus de JARVIS
        try:
            import websocket  # websocket-client

            ws = websocket.create_connection("ws://localhost:8765", timeout=5)
            ws.send(json.dumps({"event": event, "payload": payload}))
            ws.close()
        except Exception as e:
            self.logger.error(f"Error enviando WebSocket a EventBus: {e}")


def main() -> None:
    chronos = Chronos(simulate=True)
    chronos.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        chronos.stop()


if __name__ == "__main__":
    main()
