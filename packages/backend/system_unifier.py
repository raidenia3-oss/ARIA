"""System unifier for AURA - Module 26.

Registro unificado de todos los gestores (Tenants, Monitoring, Analytics,
Spatial/JARVIS, Autonomous Learner, etc.), puente de eventos y orquestador global.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from backend.event_bus import EventBus, EventSubscriber
from backend.self_healing import AURA_MODULES


@dataclass
class RegisteredSystem:
    name: str
    module: str
    instance: Any = None
    health_status: str = "registered"
    capabilities: List[str] = field(default_factory=list)


class CoreSystemRegistry:
    """Registro unificado de todos los gestores del ecosistema AURA (26 módulos)."""

    def __init__(self) -> None:
        self.systems: Dict[str, RegisteredSystem] = {}
        self._init_default_systems()

    def _init_default_systems(self) -> None:
        defaults: List[tuple] = [
            ("Aurora Core API", "aurora_core_api", ["api", "auth"]),
            ("AI Engine", "ai_engine", ["llm", "routing"]),
            ("Narrative Engine", "narrative_engine", ["storytelling", "tone"]),
            ("Mobile Automation", "mobile_automation", ["automation", "earnings"]),
            ("Self-Learning", "self_learning", ["improvement", "training"]),
            ("Fanfic Engine", "fanfic_engine", ["fanfic", "content"]),
            ("Analytics Engine", "analytics_engine", ["analytics", "usage", "sla"]),
            ("Billing Engine", "billing_engine", ["billing", "costs", "budget"]),
            ("Localization", "localization", ["i18n", "translation"]),
            ("Security", "security", ["auth", "jwt", "encryption"]),
            ("Device Orchestration", "device_orchestration", ["devices", "cluster"]),
            ("Finetuning", "finetuning", ["training", "models"]),
            ("NOMAD", "nomad", ["deployment", "containers"]),
            ("Monitoring", "monitoring", ["metrics", "alerts"]),
            ("Voice", "voice", ["stt", "tts"]),
            ("Marketplace", "marketplace", ["apps", "monetization"]),
            ("Production Deployment", "production_deployment", ["deploy", "release"]),
            ("Tenant Management", "tenant_management", ["multi-tenant", "isolation"]),
            ("Disaster Recovery", "disaster_recovery", ["backup", "restore"]),
            ("Continuous Improvement", "continuous_improvement", ["optimization", "ml"]),
            ("Spatial Gesture Engine", "spatial_gesture_engine", ["gestures", "hand_tracking"]),
            ("JARVIS Interface", "jarvis_interface", ["voice", "hud", "memory"]),
            ("Event-Driven Architecture", "event_driven_architecture", ["events", "webhooks"]),
            ("Autonomous Learner", "autonomous_learner", ["crawling", "synthesis"]),
            ("Self-Optimization", "self_optimization", ["benchmarking", "optimization"]),
            ("System Unification", "system_unification", ["orchestration", "unification"]),
        ]
        for display_name, module_name, caps in defaults:
            self.systems[module_name] = RegisteredSystem(
                name=display_name,
                module=module_name,
                capabilities=caps,
            )

    def register(
        self,
        name: str,
        module: str,
        instance: Any = None,
        capabilities: Optional[List[str]] = None,
    ) -> None:
        self.systems[module] = RegisteredSystem(
            name=name,
            module=module,
            instance=instance,
            capabilities=capabilities or [],
        )

    def unregister(self, module: str) -> bool:
        return self.systems.pop(module, None) is not None

    def get(self, module: str) -> Optional[RegisteredSystem]:
        return self.systems.get(module)

    def list_systems(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": s.name,
                "module": k,
                "health_status": s.health_status,
                "capabilities": s.capabilities,
                "has_instance": s.instance is not None,
            }
            for k, s in self.systems.items()
        ]

    def get_health(self) -> Dict[str, Any]:
        return {
            "total_systems": len(self.systems),
            "healthy": sum(1 for s in self.systems.values() if s.health_status == "registered"),
            "systems": self.list_systems(),
        }


class UnifiedEventBusBridge:
    """Puente de eventos unificado entre todos los módulos AURA."""

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus
        self.bridge_id = f"unified-bridge-{int(time.time() * 1000)}"
        self.event_log: List[Dict[str, Any]] = []
        self._max_log = 1000
        if event_bus is not None:
            event_bus.subscribe(EventSubscriber(
                name=self.bridge_id,
                handler=self._on_event,
                event_types=["*"],
            ))

    async def _on_event(self, event: Any) -> Dict[str, Any]:
        data_keys = list(event.data.keys()) if isinstance(event.data, dict) else []
        entry: Dict[str, Any] = {
            "event_type": event.event_type,
            "bridge_id": self.bridge_id,
            "timestamp": event.timestamp,
            "data_keys": data_keys,
        }
        self.event_log.append(entry)
        if len(self.event_log) > self._max_log:
            self.event_log = self.event_log[-self._max_log :]
        return {"bridged": True, "entry": entry}

    async def publish_system_event(self, event_type: str, data: Dict[str, Any], module: str = "system") -> Dict[str, Any]:
        if self.event_bus is None:
            return {"published": False, "reason": "no_event_bus"}
        result = await self.event_bus.publish(
            f"system.{event_type}",
            {"module": module, "payload": data},
        )
        return {"published": True, "event_id": result.get("event_id")}

    def get_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.event_log[-limit:]


class SystemOrchestrator:
    """Orquestador global: despacho de comandos y coordinación de subsistemas."""

    def __init__(self, registry: Optional[CoreSystemRegistry] = None, event_bus: Optional[EventBus] = None) -> None:
        self.registry = registry or CoreSystemRegistry()
        self.event_bridge = UnifiedEventBusBridge(event_bus)
        self.command_log: List[Dict[str, Any]] = []
        self._max_log = 1000
        self.command_handlers: Dict[str, Callable[..., Any]] = {}

    def register_command_handler(self, module: str, handler: Callable[..., Any]) -> None:
        self.command_handlers[module] = handler

    def get_unified_status(self) -> Dict[str, Any]:
        health = self.registry.get_health()
        return {
            "total_systems": health["total_systems"],
            "healthy": health["healthy"],
            "systems": health["systems"],
            "event_bridge_id": self.event_bridge.bridge_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    async def dispatch_command(
        self,
        command: str,
        target: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params = params or {}
        handler = self.command_handlers.get(target)
        system = self.registry.get(target)

        entry: Dict[str, Any] = {
            "command": command,
            "target": target,
            "params": params,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "unknown",
        }

        if handler is not None:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(command, params)
                else:
                    result = handler(command, params)
                entry["status"] = "success"
                entry["result"] = result
            except Exception as exc:
                entry["status"] = "failed"
                entry["error"] = str(exc)
        elif system is not None:
            entry["status"] = "acknowledged"
            entry["result"] = f"Command '{command}' routed to '{target}' (no handler registered)"
        else:
            entry["status"] = "unknown_target"
            entry["error"] = f"Unknown target: {target}"

        self.command_log.append(entry)
        if len(self.command_log) > self._max_log:
            self.command_log = self.command_log[-self._max_log :]
        return entry

    async def orchestrate_plan(self, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for step in plan:
            result = await self.dispatch_command(
                command=step.get("command", "ping"),
                target=step.get("target", "unknown"),
                params=step.get("params", {}),
            )
            results.append(result)
        return results

    def get_command_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.command_log[-limit:]
