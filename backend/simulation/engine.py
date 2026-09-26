"""BLOQUE 99 - AURA Local Autonomous Global Simulation, Scenario Stress-Testing
& Infinite Horizon Optimization Engine.

100% local y soberano: simula entornos multi-agente sinteticos, inyecta fallos
controlados (particiones P2P, picos de memoria, saturacion de agentes) y optimiza
politicas de decision a largo plazo (horizonte infinito, gamma < 1). Sin cloud.
"""
from __future__ import annotations

import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

FAULT_TYPES = ("p2p_partition", "memory_spike", "agent_saturation", "latency_storm")
MAX_AGENTS = 512
MAX_STEPS = 100_000


@dataclass
class ScenarioConfig:
    name: str = "stress"
    agents: int = 8
    steps: int = 100
    seed: int = 42
    faults: List[Dict[str, Any]] = field(default_factory=list)
    replication_rate: float = 0.3
    gamma: float = 0.95

    def __post_init__(self) -> None:
        self.agents = max(1, min(int(self.agents), MAX_AGENTS))
        self.steps = max(1, min(int(self.steps), MAX_STEPS))
        self.replication_rate = min(max(float(self.replication_rate), 0.0), 1.0)
        self.gamma = min(max(float(self.gamma), 0.0), 0.999)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "agents": self.agents, "steps": self.steps,
            "seed": self.seed, "faults": self.faults,
            "replication_rate": self.replication_rate, "gamma": self.gamma,
        }


@dataclass
class ScenarioResult:
    scenario_id: str
    config: Dict[str, Any]
    consensus_accuracy: float
    recovery_time_ms: float
    throughput: float
    resilience: float
    faults_injected: int
    recovered: int
    status: str = "completed"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id, "config": self.config,
            "consensus_accuracy": round(self.consensus_accuracy, 4),
            "recovery_time_ms": round(self.recovery_time_ms, 2),
            "throughput": round(self.throughput, 4),
            "resilience": round(self.resilience, 4),
            "faults_injected": self.faults_injected,
            "recovered": self.recovered,
            "status": self.status, "error": self.error,
        }


class SyntheticSimulator:
    """Simulador de enjambre multi-agente 100% determinista (seed reproducible)."""

    def run(self, cfg: ScenarioConfig) -> ScenarioResult:
        t0 = time.perf_counter()
        rng = random.Random(cfg.seed)
        faults = [f for f in cfg.faults if f.get("type") in FAULT_TYPES]
        injected = recovered = 0
        correct = total = 0
        recover_ms_acc = 0.0
        fault_steps = {max(1, int(f.get("step", cfg.steps // 2))): f for f in faults}
        degraded_until = -1

        for step in range(1, cfg.steps + 1):
            if step in fault_steps:
                f = fault_steps[step]
                injected += 1
                duration = max(1, int(f.get("duration", 3)))
                degraded_until = step + duration
                base = {"p2p_partition": 40.0, "memory_spike": 80.0,
                        "agent_saturation": 60.0, "latency_storm": 30.0}[f["type"]]
                recover_ms_acc += base * duration * (1.0 - cfg.replication_rate) + rng.uniform(1, 10)
                if rng.random() < cfg.replication_rate + 0.5:
                    recovered += 1
            degraded = step <= degraded_until
            active = max(1, int(cfg.agents * (0.5 if degraded else 1.0)))
            quorum = active / 2.0
            votes = sum(rng.random() < (0.55 if degraded else 0.9) for _ in range(active))
            total += 1
            correct += 1 if votes > quorum else 0

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        consensus = correct / total if total else 0.0
        resilience = recovered / injected if injected else 1.0
        return ScenarioResult(
            scenario_id=f"sc_{uuid.uuid4().hex[:12]}",
            config=cfg.to_dict(),
            consensus_accuracy=consensus,
            recovery_time_ms=recover_ms_acc / injected if injected else 0.0,
            throughput=cfg.steps / max(elapsed_ms / 1000.0, 1e-6),
            resilience=resilience,
            faults_injected=injected,
            recovered=recovered,
        )


class InfiniteHorizonOptimizer:
    """Optimizacion de horizonte infinito: ajusta la politica (tasa de replicacion)
    maximizando el retorno descontado acumulado sum(gamma^t * r_t). Determinista."""

    def __init__(self, lr: float = 0.1, gamma: float = 0.95, tolerance: float = 1e-3,
                 max_iterations: int = 200) -> None:
        self.lr = lr
        self.gamma = gamma
        self.tolerance = tolerance
        self.max_iterations = max_iterations
        self.policy = 0.3
        self.history: List[Dict[str, Any]] = []
        self.converged = False

    def _reward(self, policy: float) -> float:
        # Deterministica: maximo interior en policy ~ 0.6 (concava).
        return 1.0 - (policy - 0.6) ** 2

    def _discounted_return(self, policy: float) -> float:
        value = 0.0
        disc = 1.0
        for _ in range(50):
            value += disc * self._reward(policy)
            disc *= self.gamma
        return value

    def optimize(self, iterations: Optional[int] = None) -> Dict[str, Any]:
        self.converged = False
        n = min(iterations or self.max_iterations, self.max_iterations)
        prev_value = float("inf")
        self.history = []
        for it in range(1, n + 1):
            value = self._discounted_return(self.policy)
            delta = abs(value - prev_value)
            self.history.append({"iteration": it, "policy": round(self.policy, 4),
                                 "discounted_return": round(value, 4),
                                 "delta": round(delta, 6) if it > 1 else None})
            if it > 1 and delta < self.tolerance:
                self.converged = True
                break
            prev_value = value
            step = self.lr / (1.0 + 0.1 * it)  # paso decreciente -> contraccion
            probe = min(1.0, max(0.0, self.policy + step))
            if self._discounted_return(probe) > value:
                self.policy = min(1.0, self.policy + step)
            else:
                self.policy = max(0.0, self.policy - step)
        return {
            "converged": self.converged, "policy": round(self.policy, 4),
            "gamma": self.gamma, "tolerance": self.tolerance,
            "iterations": len(self.history), "history": self.history,
        }

    def status(self) -> Dict[str, Any]:
        return {"policy": round(self.policy, 4), "converged": self.converged,
                "history_len": len(self.history)}

    def reset(self) -> None:
        self.policy = 0.3
        self.history = []
        self.converged = False


class SimulationEngine:
    """Motor maestro: simula, somete a estres y optimiza. Thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.results: List[ScenarioResult] = []
        self.optimizer = InfiniteHorizonOptimizer()
        self.simulator = SyntheticSimulator()

    def run_scenario(self, cfg: ScenarioConfig) -> ScenarioResult:
        with self._lock:
            res = self.simulator.run(cfg)
            self.results.append(res)
            return res

    def stress_suite(self, agents: int = 16, seed: int = 99) -> Dict[str, Any]:
        """Prueba de estres multicapa: un escenario por cada tipo de fallo."""
        out = [self.run_scenario(ScenarioConfig(
            name=f"stress_{ft}", agents=agents, steps=120, seed=seed,
            faults=[{"type": ft, "step": 40, "duration": 5}])).to_dict()
            for ft in FAULT_TYPES]
        worst = min(out, key=lambda r: r["resilience"])
        return {"scenarios": out, "worst_resilience": worst["resilience"],
                "fault_types": list(FAULT_TYPES)}

    def optimization_report(self, iterations: Optional[int] = None) -> Dict[str, Any]:
        with self._lock:
            rep = self.optimizer.optimize(iterations)
            rep["offline_only"] = True
            return rep

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {"scenarios_run": len(self.results),
                    "optimizer": self.optimizer.status(), "offline_only": True}

    def reset(self) -> None:
        with self._lock:
            self.results = []
            self.optimizer.reset()


_global: Optional[SimulationEngine] = None


def get_engine() -> SimulationEngine:
    global _global
    if _global is None:
        _global = SimulationEngine()
    return _global


def reset_engine() -> None:
    global _global
    if _global is not None:
        _global.reset()
    _global = None
