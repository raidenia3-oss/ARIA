# -*- coding: utf-8 -*-
"""AURA OS - Autonomous Daemon (v2.0 — 11 tareas paralelas).

Integrates:
- 10 agents (swarm mode)
- Marketplace
- Automation Engine
- Learning Daemon (ciclo cada 6h)
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.core import get_event_bus
from backend.revenue.revenue_aggregator import RevenueAggregator
from backend.integrations.ame_sync_manager import AMESyncManager
from backend.agents.learning_agent_fanfic import learn_fanfic_writing, write_fanfic_with_context, improve_fanfic
from backend.agents.learning_agent_general import GeneralLearningAgent
from backend.agents.antigravity_integration_agent import AntigravityIntegrationAgent
from backend.agents.agent_autoconfigurator import AgentAutoConfigurator
from backend.agents.agent_code_reviewer import code_reviewer
from backend.agents.agent_video_analyzer import video_analyzer
from backend.agents.agent_image_processor import image_processor
from backend.agents.agent_data_scientist import data_scientist
from backend.agents.agent_language_tutor import language_tutor
from backend.agents.agent_fitness_coach import fitness_coach
from backend.agents.agent_music_composer import music_composer
from backend.agents.agent_psychology_counselor import psychology_counselor
from backend.agents.agent_business_analyst import business_analyst
from backend.agents.agent_researcher import researcher
from backend.marketplace.marketplace_manager import marketplace_manager
from backend.automation.automation_engine import automation_engine
from backend.daemon.learning_daemon import learning_daemon, CYCLE_INTERVAL

logger = logging.getLogger("AURA.Daemon")


class AURADaemon:
    """Daemon autonomo de AURA con 10 tareas paralelas."""

    def __init__(self) -> None:
        self.active: bool = False
        self.pause_flag: bool = False
        self.current_tasks: List[str] = []
        self.logs: List[Dict[str, Any]] = []
        self.started_at: float = 0.0
        self.event_bus = get_event_bus()
        self.revenue_aggregator = RevenueAggregator()
        self.total_revenue: float = 0.0
        self.ame_sync = AMESyncManager()
        self.general_agent = GeneralLearningAgent()
        self.antigravity_agent = AntigravityIntegrationAgent()
        self.autoconfigurator = AgentAutoConfigurator()
        self._tasks: List[asyncio.Task] = []

    async def start_daemon(self) -> None:
        """Inicia el daemon con 10 tareas paralelas."""
        self.active = True
        self.started_at = time.time()
        self.current_tasks = [
            "research", "optimization", "monitor", "sync", "revenue",
            "learning", "autoconfig", "swarm", "marketplace", "automation",
            "learning-daemon",
        ]
        self.event_bus.emit_simple("daemon_started", {
            "timestamp": datetime.now().isoformat(),
            "tasks": self.current_tasks,
        }, agent="daemon")
        print("[DAEMON] Iniciado con 10 tareas paralelas")
        await asyncio.gather(
            self._run_research_agent(),
            self._run_self_optimization(),
            self._run_resource_monitor(),
            self._run_ame_sync_agent(),
            self._run_revenue_generators(),
            self._run_learning_agents(),
            self._run_agent_autoconfigurator(),
            self._run_agent_swarm(),
            self._run_marketplace(),
            self._run_automation_engine(),
            self._run_learning_daemon(),
        )

    async def _run_research_agent(self) -> None:
        """Tarea 1: investigacion continua."""
        print("[RESEARCH] Iniciando agente de investigacion")
        while self.active:
            try:
                from backend.agents.research_agent_advanced import run_research_cycle
                result = await run_research_cycle()
                self.event_bus.emit_simple("research_complete", {
                    "insights": result.get("insights", 0),
                    "timestamp": datetime.now().isoformat(),
                }, agent="daemon")
                print("[RESEARCH] Ciclo completo: %d insights" % result.get("insights", 0))
            except Exception as exc:
                print("[RESEARCH] Error: %s" % exc)
            await asyncio.sleep(10800)

    async def _run_self_optimization(self) -> None:
        """Tarea 2: auto-optimizacion con LoRA."""
        print("[OPT] Iniciando auto-optimizacion")
        while self.active:
            try:
                from backend.ml.lora_lightweight_trainer import train_lora_lightweight
                result = await train_lora_lightweight([])
                self.event_bus.emit_simple("lora_trained", {
                    "improvement": result.get("improvement", 0),
                    "adapter_path": result.get("adapter_path", ""),
                    "timestamp": datetime.now().isoformat(),
                }, agent="daemon")
                print("[OPT] LoRA entrenado: +%.1f%%" % (result.get("improvement", 0) * 100))
            except Exception as exc:
                print("[OPT] Error: %s" % exc)
            await asyncio.sleep(604800)

    async def _run_resource_monitor(self) -> None:
        """Tarea 3: monitor de recursos."""
        print("[MONITOR] Iniciando monitor de recursos")
        while self.active:
            try:
                from backend.daemon.resource_monitor import get_all_resources
                res = get_all_resources()
                cpu = res.get("cpu_percent", 0)
                ram = res.get("ram_percent", 0)
                if cpu > 80 or ram > 90:
                    self.pause_flag = True
                    self.event_bus.emit_simple("resources_high", {
                        "cpu": cpu, "ram": ram,
                        "timestamp": datetime.now().isoformat(),
                    }, agent="daemon")
                    print("[MONITOR] Recursos altos: CPU=%s%% RAM=%s%%" % (cpu, ram))
                else:
                    self.pause_flag = False
                    self.event_bus.emit_simple("resources_ok", {
                        "cpu": cpu, "ram": ram,
                        "timestamp": datetime.now().isoformat(),
                    }, agent="daemon")
            except Exception as exc:
                print("[MONITOR] Error: %s" % exc)
            await asyncio.sleep(300)

    async def _run_ame_sync_agent(self) -> None:
        """Tarea 4: sync bidireccional PC <-> AME."""
        print("[AME_SYNC] Sincronizando con mobile...")
        while self.active:
            try:
                if self.pause_flag:
                    await asyncio.sleep(60)
                    continue
                result = await self.ame_sync.sync_bidirectional()
                self.event_bus.emit_simple("ame_sync_complete", {
                    "lora_sent_mb": result["lora_sent_mb"],
                    "insights_received": result["insights_received"],
                    "timestamp": result["timestamp"],
                }, agent="daemon")
                print("[AME_SYNC] %d insights recibidos" % result["insights_received"])
                await asyncio.sleep(7200)
            except Exception as exc:
                self.event_bus.emit_simple("ame_sync_error", {"error": str(exc), "timestamp": datetime.now().isoformat()}, agent="daemon")
                print("[AME_SYNC] Error: %s" % exc)
                await asyncio.sleep(600)

    async def _run_revenue_generators(self) -> None:
        """Tarea 5: generadores de ingresos."""
        print("[REVENUE] Iniciando generadores de ingresos")
        while self.active:
            try:
                if self.pause_flag:
                    await asyncio.sleep(60)
                    continue
                self.event_bus.emit_simple("revenue_cycle_start", {
                    "timestamp": datetime.now().isoformat(),
                }, agent="daemon")
                result = await self.revenue_aggregator.run_all_generators()
                self.total_revenue += result["total_earned"]
                self.event_bus.emit_simple("revenue_cycle_complete", {
                    "cycle_earnings": result["total_earned"],
                    "total_earned_today": self.total_revenue,
                    "by_source": result["by_source"],
                    "timestamp": datetime.now().isoformat(),
                }, agent="daemon")
                print("[REVENUE] Ciclo: +$%.2f, Total HOY: $%.2f" % (
                    result["total_earned"], self.total_revenue
                ))
            except Exception as exc:
                self.event_bus.emit_simple("revenue_error", {
                    "error": str(exc),
                    "timestamp": datetime.now().isoformat(),
                }, agent="daemon")
                print("[REVENUE] Error: %s" % exc)
            await asyncio.sleep(3600)

    async def _run_learning_agents(self) -> None:
        """Tarea 6: agentes de aprendizaje."""
        print("[LEARNING] Agentes de aprendizaje iniciados...")
        while self.active:
            try:
                if self.pause_flag:
                    await asyncio.sleep(60)
                    continue

                fanfic_lora = await learn_fanfic_writing()
                self.event_bus.emit_simple("fanfic_lora_trained", {
                    "adapter_path": fanfic_lora,
                    "timestamp": datetime.now().isoformat(),
                }, agent="learning")
                print("[LEARNING] Fanfic LoRA entrenado")

                general_insights = await self.general_agent.learn_all()
                self.event_bus.emit_simple("general_learning_complete", {
                    "insights": general_insights,
                    "total_insights": general_insights.get("total_insights", 0),
                    "timestamp": datetime.now().isoformat(),
                }, agent="learning")
                print("[LEARNING] General learning: %d insights" % general_insights.get("total_insights", 0))

                code_improvements = await self.antigravity_agent.improve_codebase()
                self.event_bus.emit_simple("code_improved", {
                    "files_processed": code_improvements.get("files_processed", 0),
                    "results": code_improvements.get("results", {}),
                    "timestamp": datetime.now().isoformat(),
                }, agent="learning")
                print("[LEARNING] Code improved: %d files" % code_improvements.get("files_processed", 0))

                await asyncio.sleep(14400)

            except Exception as exc:
                self.event_bus.emit_simple("learning_error", {
                    "error": str(exc),
                    "timestamp": datetime.now().isoformat(),
                }, agent="learning")
                print("[LEARNING] Error: %s" % exc)
                await asyncio.sleep(600)

    async def _run_agent_autoconfigurator(self) -> None:
        """Tarea 7: auto-configura agentes."""
        print("[AUTOCONFIG] Iniciando auto-configurador de agentes")
        while self.active:
            try:
                cycle = await self.autoconfigurator.run_full_cycle()
                self.event_bus.emit_simple("agents_autotuned", {
                    "cycle_id": cycle.get("cycle_id"),
                    "plan_id": cycle.get("plan", {}).get("plan_id"),
                    "applied": cycle.get("applied", {}).get("applied", 0),
                    "verified": len(cycle.get("verified", [])),
                    "timestamp": datetime.now().isoformat(),
                }, agent="autoconfig")
                print("[AUTOCONFIG] Ciclo completo: %s", cycle.get("cycle_id"))
                await asyncio.sleep(86400)

            except Exception as exc:
                self.event_bus.emit_simple("autoconfig_error", {"error": str(exc)}, agent="autoconfig")
                print("[AUTOCONFIG] Error: %s" % exc)
                await asyncio.sleep(3600)

    async def _run_agent_swarm(self) -> None:
        """Tarea 8: ejecuta todos los agentes en paralelo (swarm)."""
        print("[SWARM] Agent swarm iniciado...")
        swarm_agents = [
            ("code_reviewer", code_reviewer),
            ("video_analyzer", video_analyzer),
            ("image_processor", image_processor),
            ("data_scientist", data_scientist),
            ("language_tutor", language_tutor),
            ("fitness_coach", fitness_coach),
            ("music_composer", music_composer),
            ("psychology_counselor", psychology_counselor),
            ("business_analyst", business_analyst),
            ("researcher", researcher),
        ]

        while self.active:
            try:
                if self.pause_flag:
                    await asyncio.sleep(60)
                    continue

                tasks = []
                for name, agent in swarm_agents[:4]:
                    tasks.append(self._swarm_agent_task(name, agent))

                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, (name, _) in enumerate(swarm_agents[:4]):
                    if isinstance(results[i], Exception):
                        self.event_bus.emit_simple("swarm_error", {
                            "agent": name,
                            "error": str(results[i]),
                            "timestamp": datetime.now().isoformat(),
                        }, agent="swarm")
                    else:
                        self.event_bus.emit_simple("swarm_complete", {
                            "agent": name,
                            "result": "ok",
                            "timestamp": datetime.now().isoformat(),
                        }, agent="swarm")

                print("[SWARM] Batch completado")
                await asyncio.sleep(3600)

            except Exception as exc:
                self.event_bus.emit_simple("swarm_error", {"error": str(exc)}, agent="swarm")
                print("[SWARM] Error: %s" % exc)
                await asyncio.sleep(600)

    async def _swarm_agent_task(self, name: str, agent: Any) -> Dict[str, Any]:
        """Ejecuta un agente del swarm."""
        try:
            if hasattr(agent, "review_code"):
                result = await agent.review_code("sample code")
            elif hasattr(agent, "extract_transcript"):
                result = await agent.extract_transcript("https://example.com/video")
            elif hasattr(agent, "ocr_image"):
                result = await agent.ocr_image("data:image;base64,abc")
            elif hasattr(agent, "analyze_dataset"):
                result = await agent.analyze_dataset({"rows": 100, "columns": 5})
            elif hasattr(agent, "teach_language"):
                result = await agent.teach_language("Spanish", "B1")
            elif hasattr(agent, "generate_workout"):
                result = await agent.generate_workout("medium")
            elif hasattr(agent, "generate_melody"):
                result = await agent.generate_melody("electronic", 120)
            elif hasattr(agent, "listen_and_analyze"):
                result = await agent.listen_and_analyze("I feel anxious about the future")
            elif hasattr(agent, "analyze_market"):
                result = await agent.analyze_market("TechCorp")
            elif hasattr(agent, "search_academic"):
                result = await agent.search_academic("AI")
            else:
                result = {"status": "no_action"}

            return {"agent": name, "result": result}
        except Exception as exc:
            return {"agent": name, "error": str(exc)}

    async def _run_marketplace(self) -> None:
        """Tarea 9: procesa ventas, calcula royalties."""
        print("[MARKETPLACE] Iniciando marketplace...")
        while self.active:
            try:
                if self.pause_flag:
                    await asyncio.sleep(60)
                    continue

                royalties = await marketplace_manager.earn_royalties()
                self.event_bus.emit_simple("marketplace_cycle", {
                    "total_earnings": royalties.get("total_earnings", 0),
                    "total_sales": royalties.get("total_sales", 0),
                    "by_category": royalties.get("by_category", {}),
                    "timestamp": datetime.now().isoformat(),
                }, agent="marketplace")
                print("[MARKETPLACE] Cycle: $%.2f, %d sales" % (
                    royalties.get("total_earnings", 0),
                    royalties.get("total_sales", 0),
                ))

                recommendations = await marketplace_manager.recommend_products()
                self.event_bus.emit_simple("marketplace_recommendations", {
                    "trending": len(recommendations.get("trending", [])),
                    "new_releases": len(recommendations.get("new_releases", [])),
                    "timestamp": datetime.now().isoformat(),
                }, agent="marketplace")

                await asyncio.sleep(7200)

            except Exception as exc:
                self.event_bus.emit_simple("marketplace_error", {"error": str(exc)}, agent="marketplace")
                print("[MARKETPLACE] Error: %s" % exc)
                await asyncio.sleep(600)

    async def _run_automation_engine(self) -> None:
        """Tarea 10: ejecuta workflows de automatizacion."""
        print("[AUTOMATION] Motor de automatizacion iniciado...")
        while self.active:
            try:
                if self.pause_flag:
                    await asyncio.sleep(60)
                    continue

                status = await automation_engine.monitor_automations()
                self.event_bus.emit_simple("automation_status", {
                    "total": status.get("total_automations", 0),
                    "active": status.get("active", 0),
                    "triggered": status.get("total_triggered", 0),
                    "timestamp": datetime.now().isoformat(),
                }, agent="automation")

                active_autos = [a for a in self._get_automation_configs() if a.get("trigger", "").startswith("every")]
                if active_autos:
                    for auto_cfg in active_autos[:2]:
                        result = await automation_engine.execute_automation(auto_cfg["automation_id"])
                        self.event_bus.emit_simple("automation_executed", {
                            "automation_id": result.get("automation_id"),
                            "status": result.get("status"),
                            "duration_ms": result.get("total_duration_ms", 0),
                            "timestamp": datetime.now().isoformat(),
                        }, agent="automation")

                print("[AUTOMATION] Cycle complete")
                await asyncio.sleep(600)

            except Exception as exc:
                self.event_bus.emit_simple("automation_error", {"error": str(exc)}, agent="automation")
                print("[AUTOMATION] Error: %s" % exc)
                await asyncio.sleep(600)

    async def _run_learning_daemon(self) -> None:
        """Tarea 11: ciclo de aprendizaje autónomo cada 6h."""
        print("[LEARNING-DAEMON] Iniciando daemon de aprendizaje")
        while self.active:
            try:
                if self.pause_flag:
                    await asyncio.sleep(60)
                    continue
                result = await learning_daemon.run_cycle()
                self.event_bus.emit_simple("learning_cycle_complete", {
                    "cycle": result.get("cycle"),
                    "success": result.get("success", False),
                    "timestamp": datetime.now().isoformat(),
                }, agent="learning-daemon")
                print("[LEARNING-DAEMON] Ciclo %d completo" % result.get("cycle", 0))
            except Exception as exc:
                self.event_bus.emit_simple("learning_daemon_error", {"error": str(exc)}, agent="learning-daemon")
                print("[LEARNING-DAEMON] Error: %s" % exc)
            await asyncio.sleep(CYCLE_INTERVAL)

    def _get_automation_configs(self) -> List[Dict[str, Any]]:
        """Retorna configs de automatizacion para ejecutar."""
        return [
            {"automation_id": f"AUTO-{i}", "trigger": "every hour", "action": "health_check"}
            for i in range(3)
        ]

    def get_status(self) -> Dict[str, Any]:
        """Retorna estado actual del daemon."""
        uptime = (time.time() - self.started_at) / 3600 if self.started_at else 0
        return {
            "daemon_active": self.active,
            "current_tasks": len(self.current_tasks),
            "task_names": self.current_tasks,
            "timestamp": datetime.now().isoformat(),
            "uptime_hours": round(uptime, 2),
            "total_revenue_usd": round(self.total_revenue, 2),
        }

    async def stop_daemon(self) -> None:
        """Detiene el daemon."""
        self.active = False
        self.current_tasks = []
        self.event_bus.emit_simple("daemon_stopped", {
            "timestamp": datetime.now().isoformat(),
        }, agent="daemon")
        print("[DAEMON] Detenido")


_daemon: Optional[AURADaemon] = None


def get_daemon() -> AURADaemon:
    """Singleton accessor for AURADaemon."""
    global _daemon
    if _daemon is None:
        _daemon = AURADaemon()
    return _daemon
