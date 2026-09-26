"""Self-healing runtime for AURA - Module 26.

Detección de fallos en runtime para los 26 subsistemas, aislamiento con
patrones Circuit Breaker y recuperación automática sin caídas de la aplicación.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


AURA_MODULES: List[str] = [
    "aurora_core_api",
    "ai_engine",
    "narrative_engine",
    "mobile_automation",
    "self_learning",
    "fanfic_engine",
    "analytics_engine",
    "billing_engine",
    "localization",
    "security",
    "device_orchestration",
    "finetuning",
    "nomad",
    "monitoring",
    "voice",
    "marketplace",
    "production_deployment",
    "tenant_management",
    "disaster_recovery",
    "continuous_improvement",
    "spatial_gesture_engine",
    "jarvis_interface",
    "event_driven_architecture",
    "autonomous_learner",
    "self_optimization",
    "system_unification",
]


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class AnomalyLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class CircuitBreakerOpenError(Exception):
    """Lanzado cuando el circuit breaker está abierto y rechaza la llamada."""


@dataclass
class Anomaly:
    module: str
    metric: str
    value: float
    threshold: float
    level: str
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "level": self.level,
            "detected_at": self.detected_at,
        }


class AnomalyDetector:
    """Detección de anomalías en métricas de subsistemas vía umbrales."""

    DEFAULT_THRESHOLDS: Dict[str, Dict[str, float]] = {
        "error_rate": {"max": 0.05, "min": 0.0},
        "latency_ms": {"max": 500.0, "min": 0.0},
        "cpu_percent": {"max": 90.0, "min": 0.0},
        "memory_percent": {"max": 85.0, "min": 0.0},
        "queue_depth": {"max": 1000, "min": 0},
    }

    def __init__(self) -> None:
        self.thresholds: Dict[str, Dict[str, Dict[str, float]]] = {}
        self.anomalies: List[Anomaly] = []
        self._max_anomalies = 1000

    def set_thresholds(self, module: str, thresholds: Optional[Dict[str, Dict[str, float]]] = None) -> None:
        self.thresholds[module] = thresholds or dict(self.DEFAULT_THRESHOLDS)

    def detect(self, module: str, metrics: Dict[str, float]) -> List[Anomaly]:
        module_thresholds = self.thresholds.get(module, self.DEFAULT_THRESHOLDS)
        found: List[Anomaly] = []
        for metric, value in metrics.items():
            thresh = module_thresholds.get(metric)
            if not thresh:
                continue
            max_val = thresh.get("max", float("inf"))
            min_val = thresh.get("min", float("-inf"))
            level: Optional[str] = None
            if value > max_val:
                level = AnomalyLevel.CRITICAL if value > max_val * 2 else AnomalyLevel.WARNING
            elif value < min_val:
                level = AnomalyLevel.CRITICAL
            if level:
                anomaly = Anomaly(
                    module=module,
                    metric=metric,
                    value=float(value),
                    threshold=max_val,
                    level=level,
                )
                self.anomalies.append(anomaly)
                if len(self.anomalies) > self._max_anomalies:
                    self.anomalies = self.anomalies[-self._max_anomalies :]
                found.append(anomaly)
        return found

    def recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in self.anomalies[-limit:]]


class CircuitBreaker:
    """Aislamiento de fallos con patrón Circuit Breaker (CLOSED/OPEN/HALF_OPEN)."""

    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self.last_success_time: float = 0.0

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time < self.recovery_timeout:
                raise CircuitBreakerOpenError(self.name)
            self.state = CircuitState.HALF_OPEN

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    def record_success(self) -> None:
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_success_time = time.time()

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def reset(self) -> None:
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.last_success_time = 0.0

    def get_state_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_sec": self.recovery_timeout,
            "last_failure_epoch": self.last_failure_time,
            "last_success_epoch": self.last_success_time,
        }


class AutoRecoveryEngine:
    """Reinicia y recupera componentes dañados sin caer la aplicación."""

    def __init__(self) -> None:
        self.recovery_actions: Dict[str, Callable[[], Any]] = {}
        self.recovery_history: List[Dict[str, Any]] = []

    def register_recovery(self, module: str, action: Callable[[], Any]) -> None:
        self.recovery_actions[module] = action

    def recover(self, module: str, reason: str = "anomaly") -> Dict[str, Any]:
        action = self.recovery_actions.get(module)
        entry: Dict[str, Any] = {
            "module": module,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "success": False,
        }
        if not action:
            entry["result"] = "no_recovery_strategy_registered"
            self.recovery_history.append(entry)
            return entry
        try:
            result = action()
            entry["success"] = True
            entry["result"] = result if isinstance(result, str) else "recovered"
        except Exception as exc:
            entry["result"] = "recovery_failed"
            entry["error"] = str(exc)
        self.recovery_history.append(entry)
        if len(self.recovery_history) > 500:
            self.recovery_history = self.recovery_history[-500 :]
        return entry

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.recovery_history[-limit:]


class SelfHealingRuntime:
    """Runtime autónomo de auto-reparación para los 26 subsistemas AURA."""

    def __init__(self) -> None:
        self.module_names: List[str] = list(AURA_MODULES)
        self.anomaly_detector = AnomalyDetector()
        self.recovery_engine = AutoRecoveryEngine()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.health_metrics: Dict[str, Dict[str, Any]] = {}
        self._init_breakers()

    def _init_breakers(self) -> None:
        for module in self.module_names:
            self.circuit_breakers[module] = CircuitBreaker(
                name=module,
                failure_threshold=3,
                recovery_timeout=15.0,
            )
            self.anomaly_detector.set_thresholds(module)

    def register_recovery(self, module: str, action: Callable[[], Any]) -> None:
        self.recovery_engine.register_recovery(module, action)

    async def monitor(self, metrics: Optional[Dict[str, Dict[str, float]]] = None) -> Dict[str, Any]:
        if metrics is None:
            metrics = self.health_metrics
        all_anomalies: List[Anomaly] = []
        for module, mod_metrics in metrics.items():
            if isinstance(mod_metrics, dict):
                anomalies = self.anomaly_detector.detect(module, mod_metrics)
                all_anomalies.extend(anomalies)
                for _ in anomalies:
                    breaker = self.circuit_breakers.get(module)
                    if breaker and breaker.state != CircuitState.OPEN:
                        breaker.record_failure()
        return {
            "monitored_modules": len(metrics),
            "anomalies_found": len(all_anomalies),
            "anomalies": [a.to_dict() for a in all_anomalies],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    async def heal(self, module: str, reason: str = "manual_trigger") -> Dict[str, Any]:
        breaker = self.circuit_breakers.get(module)
        if breaker and breaker.state == CircuitState.OPEN:
            breaker.reset()
        recovery = self.recovery_engine.recover(module, reason)
        return {
            "module": module,
            "breaker_state": breaker.get_state_dict() if breaker else None,
            "recovery": recovery,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def health_report(self) -> Dict[str, Any]:
        modules_status: List[Dict[str, Any]] = []
        for name in self.module_names:
            breaker = self.circuit_breakers.get(name)
            metrics = self.health_metrics.get(name, {})
            modules_status.append({
                "module": name,
                "circuit_state": breaker.state.value if breaker else "unknown",
                "failure_count": breaker.failure_count if breaker else 0,
                "available": breaker.state != CircuitState.OPEN if breaker else True,
                "last_metrics": metrics,
            })
        return {
            "total_modules": len(self.module_names),
            "healthy": sum(1 for m in modules_status if m["circuit_state"] == "closed"),
            "degraded": sum(1 for m in modules_status if m["circuit_state"] == "half_open"),
            "critical": sum(1 for m in modules_status if m["circuit_state"] == "open"),
            "recent_anomalies": len(self.anomaly_detector.anomalies),
            "recent_recoveries": len(self.recovery_engine.recovery_history),
            "modules": modules_status,
            "anomalies": self.anomaly_detector.recent(20),
            "recoveries": self.recovery_engine.history(20),
        }


class ProcessMonitor:
    """Monitorea procesos/hilos bloqueados y buffers saturados."""

    def __init__(self) -> None:
        self._stuck_threads: List[Dict[str, Any]] = []
        self._buffer_overflows: List[Dict[str, Any]] = []
        self._ws_reconnects: List[Dict[str, Any]] = []

    def check_threads(self, threads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        stuck = [t for t in threads if t.get("alive") and not t.get("busy", True)]
        self._stuck_threads.extend(stuck)
        self._stuck_threads = self._stuck_threads[-50:]
        return stuck

    def record_buffer_overflow(self, source: str, size: int, limit: int) -> Dict[str, Any]:
        entry = {"source": source, "size": size, "limit": limit, "timestamp": time.time()}
        self._buffer_overflows.append(entry)
        self._buffer_overflows = self._buffer_overflows[-50:]
        return entry

    def record_ws_reconnect(self, endpoint: str, success: bool, latency: float) -> Dict[str, Any]:
        entry = {"endpoint": endpoint, "success": success, "latency": latency, "timestamp": time.time()}
        self._ws_reconnects.append(entry)
        self._ws_reconnects = self._ws_reconnects[-50:]
        return entry

    def status(self) -> Dict[str, Any]:
        return {
            "stuck_threads": len(self._stuck_threads),
            "buffer_overflows": len(self._buffer_overflows),
            "ws_reconnects": len(self._ws_reconnects),
            "recent_stuck": self._stuck_threads[-5:],
            "recent_overflows": self._buffer_overflows[-5:],
            "recent_reconnects": self._ws_reconnects[-5:],
        }


class SilentReconnector:
    """Reconexión silenciosa de sockets con backoff exponencial."""

    def __init__(self, max_attempts: int = 8, base_delay: float = 1.0, max_delay: float = 10.0) -> None:
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._attempts: Dict[str, int] = {}

    def next_delay(self, endpoint: str) -> float:
        attempt = self._attempts.get(endpoint, 0)
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        self._attempts[endpoint] = attempt + 1
        return delay

    def reset(self, endpoint: str) -> None:
        self._attempts[endpoint] = 0


self_healing = SelfHealingRuntime()
process_monitor = ProcessMonitor()
silent_reconnector = SilentReconnector()
