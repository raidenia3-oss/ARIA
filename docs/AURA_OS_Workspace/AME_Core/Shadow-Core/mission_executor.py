#!/usr/bin/env python3
"""
mission_executor.py — AURA Mission Executor
============================================
Motor de ejecución de misiones complejas definidas en missions.yaml.
Maneja el estado (Iniciada, Paso X completado, Fallida), reintentos
automáticos y alertas a WhatsApp si un paso falla después de reintentos.

Uso:
  executor = MissionExecutor()
  mission = executor.start_mission("deep_scan", target="192.168.1.0/24")
  executor.wait_for_completion()
"""

import os
import sys
import json
import time
import yaml
import logging
import threading
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [MISSION] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('mission_executor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Constantes ──
MISSIONS_FILE = Path(__file__).resolve().parent / "missions.yaml"
RESULTS_DIR = Path(__file__).resolve().parent / "mission_results"
ROOT_DIR = Path(__file__).resolve().parent.parent
AURA_CORE_DIR = ROOT_DIR / "AURA_Core"


# ─── Estados de la Misión ───

class MissionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    STEP_RUNNING = "step_running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


@dataclass
class StepResult:
    step_id: str
    status: StepStatus
    result: Any = None
    error: str = ""
    duration_ms: float = 0
    retries_used: int = 0

@dataclass
class MissionState:
    mission_id: str
    mission_name: str
    status: MissionStatus
    started_at: str = ""
    completed_at: str = ""
    current_step: int = 0
    total_steps: int = 0
    steps_results: Dict[str, StepResult] = field(default_factory=dict)
    parameters: Dict = field(default_factory=dict)
    step_results_data: Dict = field(default_factory=dict)  # Variables inter-paso


class MissionExecutor:
    """
    Ejecutor de misiones complejas.
    Lee misiones de missions.yaml y ejecuta cada paso secuencialmente,
    manejando reintentos, dependencias y alertas.
    """

    def __init__(self, notification_bridge=None, swarm_manager=None):
        self.bridge = notification_bridge
        self.swarm_manager = swarm_manager
        self.missions_config = self._load_missions()
        self.active_missions: Dict[str, MissionState] = {}
        self.lock = threading.Lock()
        self.running = False
        self._module_cache: Dict[str, Any] = {}

    def _load_missions(self) -> Dict:
        """Carga las misiones desde missions.yaml."""
        try:
            with open(MISSIONS_FILE, 'r') as f:
                config = yaml.safe_load(f)
            n_missions = len(config.get("missions", {}))
            logger.info(f"Cargadas {n_missions} misiones desde {MISSIONS_FILE}")
            return config
        except Exception as e:
            logger.error(f"Error cargando missions.yaml: {e}")
            return {"missions": {}, "global": {"max_retries": 3, "retry_delay": 10}}

    def list_missions(self) -> List[Dict]:
        """Lista todas las misiones disponibles."""
        missions = []
        for mission_id, mission_cfg in self.missions_config.get("missions", {}).items():
            missions.append({
                "id": mission_id,
                "name": mission_cfg.get("name", mission_id),
                "description": mission_cfg.get("description", ""),
                "priority": mission_cfg.get("priority", "medium"),
                "steps": len(mission_cfg.get("steps", [])),
                "timeout": mission_cfg.get("timeout", 300)
            })
        return missions

    def start_mission(self, mission_id: str, **parameters) -> Optional[MissionState]:
        """Inicia y ejecuta una misión de forma asíncrona."""
        mission_cfg = self.missions_config.get("missions", {}).get(mission_id)
        if not mission_cfg:
            logger.error(f"Misión '{mission_id}' no encontrada en missions.yaml")
            return None

        # Crear estado de la misión
        state = MissionState(
            mission_id=mission_id,
            mission_name=mission_cfg.get("name", mission_id),
            status=MissionStatus.RUNNING,
            started_at=datetime.now().isoformat(),
            total_steps=len(mission_cfg.get("steps", [])),
            parameters=parameters
        )

        with self.lock:
            self.active_missions[mission_id] = state

        # Ejecutar en hilo separado
        thread = threading.Thread(
            target=self._execute_mission,
            args=(mission_id, mission_cfg, state),
            daemon=True
        )
        thread.start()

        logger.info(f"🚀 Misión '{state.mission_name}' iniciada (ID: {mission_id})")
        return state

    def _execute_mission(self, mission_id: str, config: Dict, state: MissionState):
        """Ejecuta los pasos de una misión secuencialmente."""
        steps = config.get("steps", [])
        global_config = self.missions_config.get("global", {})
        max_retries = config.get("max_retries", global_config.get("max_retries", 3))
        retry_delay = global_config.get("retry_delay", 10)

        # Resolver dependencias (orden topológico)
        ordered_steps = self._resolve_dependencies(steps)

        for i, step in enumerate(ordered_steps):
            if state.status == MissionStatus.CANCELLED:
                logger.info(f"⏹ Misión {mission_id} cancelada")
                break

            step_id = step.get("id", f"step_{i}")
            step_name = step.get("name", step_id)
            step_max_retries = step.get("max_retries", max_retries)
            step_timeout = step.get("timeout", 60)

            logger.info(f"  ▶ Paso {i+1}/{len(ordered_steps)}: {step_name}")
            state.current_step = i + 1

            # Ejecutar paso con reintentos
            success = False
            retries_used = 0

            for attempt in range(step_max_retries + 1):
                if state.status == MissionStatus.CANCELLED:
                    break

                step_result = self._execute_step(step, state.step_results_data, step_timeout)
                state.steps_results[step_id] = step_result

                if step_result.status == StepStatus.COMPLETED:
                    # Guardar resultado para pasos siguientes
                    state.step_results_data[f"step_{i+1}"] = step_result.result
                    success = True
                    logger.info(f"    ✅ {step_name} completado ({step_result.duration_ms:.0f}ms)")
                    break
                else:
                    retries_used += 1
                    step_result.retries_used = retries_used
                    if attempt < step_max_retries:
                        logger.warning(f"    ⚠️ {step_name} falló (intento {attempt+1}/{step_max_retries}), reintentando en {retry_delay}s...")
                        state.steps_results[step_id] = step_result
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"    ❌ {step_name} falló tras {step_max_retries} reintentos")
                        break

            if not success and state.status != MissionStatus.CANCELLED:
                state.status = MissionStatus.FAILED
                state.completed_at = datetime.now().isoformat()

                # Ejecutar on_failure
                self._execute_hooks(config.get("on_failure", []), state)

                # Alertar a WhatsApp
                self._send_failure_alert(state, step_name)
                logger.error(f"❌ Misión '{state.mission_name}' FALLIDA en paso '{step_name}'")
                self._save_results(state)
                return

        # ¡Misión completada!
        if state.status != MissionStatus.CANCELLED:
            state.status = MissionStatus.COMPLETED
            state.completed_at = datetime.now().isoformat()

            # Ejecutar on_complete
            self._execute_hooks(config.get("on_complete", []), state)

            logger.info(f"✅ Misión '{state.mission_name}' COMPLETADA exitosamente")
            self._save_results(state)

    def _execute_step(self, step: Dict, context: Dict, timeout: int) -> StepResult:
        """Ejecuta un paso individual de la misión."""
        step_id = step.get("id", "unknown")
        start = time.time()

        try:
            module_name = step.get("module", "")
            action = step.get("action", "")
            parameters = step.get("parameters", {})

            # Resolver plantillas en parámetros
            resolved_params = self._resolve_templates(parameters, context)

            # Ejecutar el módulo correspondiente
            result = self._call_module_action(module_name, action, resolved_params, context)

            duration = (time.time() - start) * 1000
            return StepResult(
                step_id=step_id,
                status=StepStatus.COMPLETED,
                result=result,
                duration_ms=duration
            )

        except Exception as e:
            duration = (time.time() - start) * 1000
            return StepResult(
                step_id=step_id,
                status=StepStatus.FAILED,
                error=str(e),
                duration_ms=duration
            )

    def _call_module_action(self, module_name: str, action: str,
                            parameters: Dict, context: Dict) -> Any:
        """
        Llama a la acción correspondiente del módulo.
        Simula la ejecución en entorno de desarrollo.
        """
        logger.info(f"    🔧 Ejecutando {module_name}.{action}")

        # Simulación de ejecución (en producción se integraría con los módulos reales)
        import random
        import time
        simulated_delay = random.uniform(0.1, 1.0)
        time.sleep(simulated_delay)

        # Resultado simulado según el módulo y acción
        if module_name == "network_sensor":
            if action in ("full_scan", "threat_scan"):
                return {
                    "total_devices": random.randint(5, 50),
                    "suspicious_ips": [f"192.168.1.{random.randint(100,200)}" for _ in range(random.randint(0,5))],
                    "node_anomalies": [f"anomaly_{i}" for i in range(random.randint(0,3))],
                    "scan_duration_ms": random.randint(1000, 10000)
                }
            elif action == "analyze_devices":
                return {
                    "vulnerable_hosts": [f"192.168.1.{random.randint(100,200)}" for _ in range(random.randint(1,5))],
                    "total_analyzed": random.randint(10, 40)
                }

        elif module_name == "osint_engine":
            if action in ("venice_audit", "quick_lookup"):
                return {
                    "vulnerabilities": random.randint(0, 10),
                    "findings": [f"finding_{i}" for i in range(random.randint(1,8))],
                    "risk_score": random.randint(20, 90),
                    "results": {"summary": f"OSINT completed for {parameters.get('target', 'unknown')}"}
                }
            elif action == "vuln_scan":
                return {
                    "vulnerabilities": random.randint(0, 5),
                    "critical": random.randint(0, 2),
                    "high": random.randint(0, 3)
                }

        elif module_name == "swarm_orchestrator":
            if action == "correlate_findings":
                return {
                    "correlated_threats": random.randint(0, 10),
                    "max_severity": random.choice(["low", "medium", "high", "critical"]),
                    "confidence": random.uniform(0.5, 1.0)
                }
            elif action == "health_check_all":
                return {
                    "nodes_online": random.randint(1, 10),
                    "nodes_offline": random.randint(0, 3),
                    "total_nodes": 10
                }
            elif action == "broadcast_command":
                return {
                    "nodes_affected": random.randint(1, 8),
                    "success_rate": random.uniform(0.7, 1.0)
                }

        elif module_name == "predictive_maintenance":
            if action == "predict_all":
                return {
                    "predictions": random.randint(0, 5),
                    "critical": random.randint(0, 2),
                    "warnings": random.randint(0, 3)
                }

        elif module_name == "notification_bridge":
            return {"sent": True, "channel": parameters.get("channel", "discord")}

        # Fallback: resultado genérico
        return {
            "status": "completed",
            "module": module_name,
            "action": action,
            "simulated": True,
            "message": f"Acción {module_name}.{action} ejecutada exitosamente"
        }

    def _resolve_dependencies(self, steps: List[Dict]) -> List[Dict]:
        """Resuelve el orden de ejecución según dependencias (topological sort)."""
        # Simplificación: ejecutar en orden secuencial, respetando depends_on
        # En producción se usaría un topological sort real
        sorted_steps = []
        remaining = list(steps)
        executed = set()

        max_iterations = len(steps) + 1
        for _ in range(max_iterations):
            if not remaining:
                break

            progress = False
            new_remaining = []

            for step in remaining:
                deps = step.get("depends_on", [])
                if isinstance(deps, str):
                    deps = [deps]

                all_deps_met = all(dep in executed for dep in deps)

                if all_deps_met:
                    sorted_steps.append(step)
                    executed.add(step.get("id", ""))
                    progress = True
                else:
                    new_remaining.append(step)

            remaining = new_remaining

            if not progress and remaining:
                # Dependencias circulares o no resueltas, ejecutar restantes en orden
                logger.warning("Dependencias circulares detectadas, ejecutando en orden secuencial")
                sorted_steps.extend(remaining)
                break

        return sorted_steps

    def _resolve_templates(self, data: Any, context: Dict) -> Any:
        """Resuelve plantillas {{step_N.field}} en datos."""
        if isinstance(data, str):
            # Buscar patrón {{...}}
            import re
            pattern = r'\{\{(.+?)\}\}'

            def replace_template(match):
                template_path = match.group(1).strip()
                parts = template_path.split('.')

                # Buscar en contexto
                current = context
                for part in parts:
                    if isinstance(current, dict):
                        current = current.get(part)
                        if current is None:
                            return match.group(0)  # No resuelto, mantener original
                    else:
                        return str(current)

                return str(current) if current is not None else match.group(0)

            return re.sub(pattern, replace_template, data)

        elif isinstance(data, dict):
            return {k: self._resolve_templates(v, context) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_templates(item, context) for item in data]
        else:
            return data

    def _execute_hooks(self, hooks: List[Dict], state: MissionState):
        """Ejecuta hooks de on_complete o on_failure."""
        for hook in hooks:
            hook_type = hook.get("type")
            try:
                if hook_type == "notify":
                    channel = hook.get("channel", "discord")
                    message = self._resolve_templates(hook.get("message", ""), state.step_results_data)
                    if self.bridge:
                        self.bridge.notify_threat_blocked(
                            threat_type="mission_result",
                            source=state.mission_name,
                            target="system",
                            severity="high" if "failed" in message.lower() else "info"
                        )
                elif hook_type == "log":
                    logger.info(f"HOOK: {hook.get('category', 'mission_event')} - {state.mission_name}")
            except Exception as e:
                logger.error(f"Error en hook {hook_type}: {e}")

    def _send_failure_alert(self, state: MissionState, failed_step: str):
        """Envía alerta a WhatsApp cuando falla una misión."""
        message = (
            f"❌ MISIÓN FALLIDA: {state.mission_name}\n"
            f"ID: {state.mission_id}\n"
            f"Paso fallido: {failed_step}\n"
            f"Pasos completados: {state.current_step - 1}/{state.total_steps}\n"
            f"Iniciada: {state.started_at}\n"
            f"Requiere intervención manual."
        )
        logger.warning(f"🚨 ALERTA: {message}")

        if self.bridge:
            self.bridge.notify_threat_blocked(
                threat_type="mission_failure",
                source=state.mission_name,
                target="system",
                severity="critical"
            )

    def _save_results(self, state: MissionState):
        """Guarda los resultados de la misión en archivo."""
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        result_file = RESULTS_DIR / f"{state.mission_id}_{state.started_at.replace(':', '-')[:19]}.json"

        result_data = {
            "mission_id": state.mission_id,
            "mission_name": state.mission_name,
            "status": state.status.value,
            "started_at": state.started_at,
            "completed_at": state.completed_at,
            "total_steps": state.total_steps,
            "parameters": state.parameters,
            "steps": {
                step_id: {
                    "status": sr.status.value,
                    "duration_ms": round(sr.duration_ms, 1),
                    "retries_used": sr.retries_used,
                    "error": sr.error
                }
                for step_id, sr in state.steps_results.items()
            }
        }

        with open(result_file, 'w') as f:
            json.dump(result_data, f, indent=2)
        logger.info(f"Resultados guardados en {result_file}")

    def get_mission_status(self, mission_id: str) -> Optional[Dict]:
        """Obtiene el estado de una misión activa."""
        state = self.active_missions.get(mission_id)
        if not state:
            return None

        return {
            "mission_id": state.mission_id,
            "name": state.mission_name,
            "status": state.status.value,
            "current_step": f"{state.current_step}/{state.total_steps}",
            "started_at": state.started_at,
            "completed_at": state.completed_at,
            "steps": {
                sid: {"status": sr.status.value, "duration_ms": round(sr.duration_ms, 1)}
                for sid, sr in state.steps_results.items()
            }
        }

    def cancel_mission(self, mission_id: str) -> bool:
        """Cancela una misión en ejecución."""
        state = self.active_missions.get(mission_id)
        if state and state.status == MissionStatus.RUNNING:
            state.status = MissionStatus.CANCELLED
            logger.info(f"⏹ Misión {mission_id} cancelada")
            return True
        return False


# ─── Punto de entrada ───
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AURA Mission Executor")
    parser.add_argument("--list", action="store_true", help="Listar misiones disponibles")
    parser.add_argument("--start", type=str, metavar="MISSION_ID", help="Iniciar una misión")
    parser.add_argument("--status", type=str, metavar="MISSION_ID", help="Ver estado de una misión")
    parser.add_argument("--cancel", type=str, metavar="MISSION_ID", help="Cancelar una misión")
    parser.add_argument("--target", type=str, help="Parámetro target para la misión")
    parser.add_argument("--results", action="store_true", help="Ver resultados recientes")
    args = parser.parse_args()

    executor = MissionExecutor()

    if args.list:
        missions = executor.list_missions()
        print("\n📋 MISIONES DISPONIBLES")
        print("=" * 60)
        for m in missions:
            priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(m["priority"], "⚪")
            print(f"\n  {priority_icon} {m['id']}")
            print(f"    Nombre: {m['name']}")
            print(f"    Descripción: {m['description'][:80]}...")
            print(f"    Pasos: {m['steps']} | Timeout: {m['timeout']}s | Prioridad: {m['priority']}")
        print()

    elif args.start:
        params = {}
        if args.target:
            params["target"] = args.target

        state = executor.start_mission(args.start, **params)
        if state:
            print(f"\n🚀 Misión '{state.mission_name}' iniciada")
            print(f"   ID: {state.mission_id}")
            print(f"   Pasos: {state.total_steps}")
            print(f"   Esperando a que termine... (Ctrl+C para cancelar)")

            try:
                while state.status == MissionStatus.RUNNING:
                    time.sleep(2)
                    status = executor.get_mission_status(state.mission_id)
                    if status:
                        print(f"   Paso {status['current_step']} | Estado: {status['status']}", end='\r')
            except KeyboardInterrupt:
                print("\n\n⏹ Cancelando misión...")
                executor.cancel_mission(state.mission_id)

            # Mostrar resultado final
            status = executor.get_mission_status(state.mission_id)
            if status:
                print(f"\n{'='*50}")
                print(f"  RESULTADO: {status['status'].upper()}")
                print(f"  Duración: {status['started_at'][:19]} → {status['completed_at'][:19] if status['completed_at'] else 'N/A'}")
                for sid, info in status['steps'].items():
                    icon = "✅" if info['status'] == 'completed' else "❌" if info['status'] == 'failed' else "⏳"
                    print(f"  {icon} {sid}: {info['status']} ({info['duration_ms']}ms)")
        else:
            print(f"❌ No se pudo iniciar la misión '{args.start}'")

    elif args.status:
        status = executor.get_mission_status(args.status)
        if status:
            print(f"\n📊 Estado: {status['name']}")
            print(f"   ID: {status['mission_id']}")
            print(f"   Status: {status['status']}")
            print(f"   Paso: {status['current_step']}")
            for sid, info in status['steps'].items():
                icon = "✅" if info['status'] == 'completed' else "❌" if info['status'] == 'failed' else "⏳"
                print(f"   {icon} {sid}: {info['status']}")
        else:
            print(f"❌ Misión '{args.status}' no encontrada o no activa")

    elif args.cancel:
        success = executor.cancel_mission(args.cancel)
        print(f"{'✅ Misión cancelada' if success else '❌ No se pudo cancelar'}")

    elif args.results:
        if RESULTS_DIR.exists():
            files = sorted(RESULTS_DIR.glob("*.json"), reverse=True)[:5]
            for f in files:
                with open(f) as fh:
                    data = json.load(fh)
                icon = "✅" if data['status'] == 'completed' else "❌"
                print(f"  {icon} {data['mission_name']}: {data['status']} ({f.name})")
        else:
            print("No hay resultados de misiones aún.")

    else:
        print("=" * 55)
        print("  AURA Mission Executor v1.0")
        print("=" * 55)
        print()
        print("  --list                    Listar misiones disponibles")
        print("  --start <mission_id>      Iniciar una misión")
        print("  --status <mission_id>     Ver estado de una misión")
        print("  --cancel <mission_id>     Cancelar una misión")
        print("  --target <ip/url>         Parámetro target para la misión")
        print("  --results                 Ver resultados recientes")
        print()
        print("  Ejemplo:")
        print("    python mission_executor.py --list")
        print("    python mission_executor.py --start deep_scan --target 192.168.1.0/24")
        print("    python mission_executor.py --start quick_osint --target example.com")
        print("    python mission_executor.py --results")