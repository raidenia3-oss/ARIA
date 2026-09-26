"""Self-Learning Manager - Autoconfiguration + aprendizaje autónomo."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class ConfigSource(Enum):
    HARDWARE = "hardware"
    LEARNED = "learned"
    OPTIMIZED = "optimized"
    DEFAULT = "default"


@dataclass
class AutoConfig:
    routing_weights: Dict[str, float]
    treasure_allocation: Dict[str, float]
    narrative_tones: Dict[str, float]
    mobile_apps_priority: List[str]
    feature_flags: Dict[str, bool]
    resource_limits: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "routing": self.routing_weights,
            "treasury": self.treasure_allocation,
            "narrative": self.narrative_tones,
            "mobile": self.mobile_apps_priority,
            "features": self.feature_flags,
            "resources": self.resource_limits,
            "updated": datetime.now().isoformat(),
        }


@dataclass
class LearningEvent:
    event_type: str
    endpoint: str
    context: Dict
    outcome: str
    timestamp: str
    learned_adjustment: Optional[Dict] = None


class AutoConfigurer:
    def __init__(self, db) -> None:
        self.db = db
        self.config: Optional[AutoConfig] = None

    async def auto_configure(self) -> AutoConfig:
        print("SelfLearning: auto-configurando...")
        hardware = await self._detect_hardware()
        self.config = AutoConfig(
            routing_weights=self._calc_routing_weights(hardware),
            treasure_allocation=self._calc_treasury_allocation(hardware),
            narrative_tones=self._init_narrative_tones(),
            mobile_apps_priority=self._rank_mobile_apps(),
            feature_flags=self._determine_features(hardware),
            resource_limits=self._set_resource_limits(hardware),
        )
        if self.db:
            learned_config = await self.db.get_learned_config()
            if learned_config:
                self._merge_learned_config(learned_config)
                print("SelfLearning: merged learned configuration")
        print("SelfLearning: auto-configuración completa")
        return self.config

    async def _detect_hardware(self) -> Dict[str, Any]:
        try:
            import psutil

            return {
                "cpu_cores": psutil.cpu_count(),
                "ram_gb": psutil.virtual_memory().total / (1024**3),
                "disk_gb": psutil.disk_usage("/").total / (1024**3),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "has_gpu": self._detect_gpu(),
                "platform": self._detect_platform(),
            }
        except Exception:
            return {
                "cpu_cores": 4,
                "ram_gb": 8,
                "disk_gb": 100,
                "cpu_percent": 0,
                "has_gpu": False,
                "platform": "unknown",
            }

    def _calc_routing_weights(self, hardware: Dict[str, Any]) -> Dict[str, float]:
        ram_gb = hardware.get("ram_gb", 8)
        cpu_cores = hardware.get("cpu_cores", 4)
        if ram_gb >= 16 and cpu_cores >= 8:
            return {"server": 0.6, "pc": 0.8, "apis": 0.5, "cache": 0.3}
        elif ram_gb >= 8 and cpu_cores >= 4:
            return {"server": 0.7, "pc": 0.6, "apis": 0.6, "cache": 0.4}
        return {"server": 0.9, "pc": 0.3, "apis": 0.5, "cache": 0.7}

    def _calc_treasury_allocation(self, hardware: Dict[str, Any]) -> Dict[str, float]:
        if hardware.get("ram_gb", 8) < 8:
            return {"apis": 0.25, "hosting": 0.50, "models": 0.15, "reserve": 0.10}
        return {"apis": 0.30, "hosting": 0.35, "models": 0.25, "reserve": 0.10}

    def _init_narrative_tones(self) -> Dict[str, float]:
        return {"dark": 0.2, "romantic": 0.15, "noir": 0.15, "dramatic": 0.3, "whimsical": 0.2}

    def _rank_mobile_apps(self) -> List[str]:
        return ["Rollercoin", "TaskRabbit", "Mistplay", "FeaturePoints", "Cashyy"]

    def _determine_features(self, hardware: Dict[str, Any]) -> Dict[str, bool]:
        ram_gb = hardware.get("ram_gb", 8)
        return {
            "narrative_engine": True,
            "mobile_automation": True,
            "federated_training": ram_gb >= 8,
            "gpu_acceleration": bool(hardware.get("has_gpu", False)),
            "multi_threading": hardware.get("cpu_cores", 4) >= 4,
            "advanced_caching": ram_gb >= 16,
        }

    def _set_resource_limits(self, hardware: Dict[str, Any]) -> Dict[str, int]:
        ram_gb = hardware.get("ram_gb", 8)
        ram_mb = max(256, int((ram_gb * 1024) // 2))
        return {
            "max_memory_mb": ram_mb,
            "max_threads": max(1, hardware.get("cpu_cores", 4) * 2),
            "max_db_size_mb": 1024,
            "cache_size_mb": max(64, ram_mb // 4),
        }

    def _detect_gpu(self) -> bool:
        try:
            import torch

            return torch.cuda.is_available()
        except Exception:
            return False

    def _detect_platform(self) -> str:
        import platform

        return platform.system()

    def _merge_learned_config(self, learned: Dict[str, Any]) -> None:
        if not self.config:
            return
        routing = learned.get("routing")
        treasury = learned.get("treasury")
        mobile = learned.get("mobile")
        if routing:
            self.config.routing_weights.update(routing)
        if treasury:
            self.config.treasure_allocation.update(treasury)
        if mobile:
            self.config.mobile_apps_priority = mobile


class ErrorLearner:
    def __init__(self, db) -> None:
        self.db = db
        self.error_log: List[LearningEvent] = []

    async def log_error(self, endpoint: str, error: Exception, context: Dict[str, Any]) -> None:
        event = LearningEvent(
            event_type="error",
            endpoint=endpoint,
            context=context,
            outcome=str(error),
            timestamp=datetime.now().isoformat(),
            learned_adjustment=await self._analyze_and_learn(endpoint, str(error)),
        )
        self.error_log.append(event)
        if self.db:
            await self.db.add_learning_event(event)
        print("SelfLearning: error registrado en %s -> %s" % (endpoint, event.learned_adjustment))

    async def _analyze_and_learn(self, endpoint: str, outcome: str) -> Dict[str, Any]:
        outcome_lower = outcome.lower()
        if "timeout" in outcome_lower:
            return {"type": "routing_adjustment", "action": "reduce_timeout_threshold", "value": -0.1}
        if "memory" in outcome_lower:
            return {"type": "resource_adjustment", "action": "reduce_cache_size", "value": -20}
        if "database" in outcome_lower:
            return {"type": "db_adjustment", "action": "increase_retry_count", "value": 3}
        if "narrative" in outcome_lower:
            return {"type": "narrative_adjustment", "action": "reduce_cliche_threshold", "value": 0.05}
        return {"type": "generic", "action": "retry"}


class ParameterOptimizer:
    def __init__(self, db, config: AutoConfig) -> None:
        self.db = db
        self.config = config
        self.optimization_history: List[Dict[str, Any]] = []

    async def continuous_optimization_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(3600)
                metrics = await self._collect_metrics()
                issues = await self._identify_issues(metrics)
                for issue in issues:
                    await self._apply_optimization(issue)
                if self.db:
                    await self.db.save_optimization_history(self.optimization_history)
                print("SelfLearning: ciclo de optimización completo, ajustes=%d" % len(issues))
            except Exception as exc:
                print("SelfLearning: error en optimización: %s" % exc)
                await asyncio.sleep(300)

    async def _collect_metrics(self) -> Dict[str, Any]:
        return {
            "avg_response_time_ms": 150,
            "error_rate_percent": 0.5,
            "cache_hit_rate": 0.85,
            "memory_usage_percent": 65,
            "cpu_usage_percent": 40,
            "routing_accuracy": 0.92,
            "narrative_cliche_score": 0.3,
        }

    async def _identify_issues(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        if metrics.get("avg_response_time_ms", 0) > 200:
            issues.append({"type": "latency", "severity": "high"})
        if metrics.get("error_rate_percent", 0) > 1.0:
            issues.append({"type": "reliability", "severity": "high"})
        if metrics.get("memory_usage_percent", 0) > 80:
            issues.append({"type": "memory", "severity": "medium"})
        if metrics.get("cache_hit_rate", 1.0) < 0.75:
            issues.append({"type": "cache_efficiency", "severity": "low"})
        return issues

    async def _apply_optimization(self, issue: Dict[str, Any]) -> None:
        issue_type = issue["type"]
        if issue_type == "latency":
            self.config.routing_weights["server"] = min(1.0, self.config.routing_weights.get("server", 0.7) * 1.1)
            self.optimization_history.append({"type": "routing_boost", "timestamp": datetime.now().isoformat()})
        elif issue_type == "reliability":
            self.optimization_history.append({"type": "reliability_retry_increase", "timestamp": datetime.now().isoformat()})
        elif issue_type == "memory":
            self.config.resource_limits["cache_size_mb"] = max(64, int(self.config.resource_limits.get("cache_size_mb", 1024) * 0.8))
            self.optimization_history.append({"type": "cache_reduce", "timestamp": datetime.now().isoformat()})
        elif issue_type == "cache_efficiency":
            self.optimization_history.append({"type": "cache_ttl_increase", "timestamp": datetime.now().isoformat()})


class SelfLearningManager:
    def __init__(self, db=None) -> None:
        self.db = db
        self.auto_config: Optional[AutoConfig] = None
        self.error_learner: Optional[ErrorLearner] = None
        self.optimizer: Optional[ParameterOptimizer] = None

    async def initialize(self) -> None:
        print("SelfLearning: inicializando...")
        self.auto_config = AutoConfig(
            routing_weights={},
            treasure_allocation={},
            narrative_tones={},
            mobile_apps_priority=[],
            feature_flags={},
            resource_limits={},
        )
        configurer = AutoConfigurer(self.db)
        self.auto_config = await configurer.auto_configure()
        self.error_learner = ErrorLearner(self.db)
        self.optimizer = ParameterOptimizer(self.db, self.auto_config)
        asyncio.create_task(self.optimizer.continuous_optimization_loop())
        print("SelfLearning: sistema listo")

    async def handle_error(self, endpoint: str, error: Exception, context: Dict[str, Any]) -> None:
        if self.error_learner:
            await self.error_learner.log_error(endpoint, error, context)

    def get_current_config(self) -> Dict[str, Any]:
        if self.auto_config:
            return self.auto_config.to_dict()
        return {}

    async def get_optimization_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.optimizer:
            return []
        return self.optimizer.optimization_history[-limit:]

    async def get_learning_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.db:
            return []
        events = await self.db.get_learning_events(limit)
        return [
            {
                "type": e.event_type,
                "endpoint": e.endpoint,
                "outcome": e.outcome,
                "learned": e.learned_adjustment,
                "timestamp": e.timestamp,
            }
            for e in events
        ]
