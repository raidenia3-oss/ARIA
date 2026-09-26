"""BLOQUE 91 - Bridge: refactoring <-> governor (71) + fusion (83) + master (100).

100% local, sin dependencias externas. Importaciones perezosas para no
acoplar los subsistemas previos (regla de no tocar Bloques 71/83/100).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def governor_gate(workload_id: str = "refactoring91") -> Dict[str, Any]:
    """Consulta al gobernador (Bloque 71). Nunca bloquea por error: fail-open."""
    try:
        from backend.telemetry.governor import get_governor
        from backend.telemetry.models import WorkloadItem

        gov = get_governor()
        try:
            gov.register_workload(WorkloadItem(
                workload_id=workload_id, name="AURA Refactoring 91",
                kind="refactoring", priority=5,
            ))
        except Exception:
            pass
        report = gov.evaluate()
        decision = getattr(report.decision, "value", str(report.decision))
        allowed = decision in ("allow", "throttle", "warn", "defer")
        # PAUSE => no permitido
        if decision == "pause":
            allowed = False
        return {
            "allowed": allowed,
            "decision": decision,
            "action": getattr(report.action, "value", str(report.action)),
            "severity": getattr(report, "severity", "info"),
            "reasons": list(getattr(report, "reasons", []) or []),
            "offline_only": True,
        }
    except Exception as exc:
        return {"allowed": True, "decision": "allow",
                "action": "none", "severity": "info",
                "reasons": [f"governor unavailable (fail-open): {exc}"],
                "offline_only": True}


def emit_fusion(kind: str, payload: Dict[str, Any],
                severity: str = "info",
                source: str = "system") -> Optional[str]:
    """Publica un evento en el bus sensorial (Bloque 83). Fail-soft."""
    try:
        from backend.fusion.sensory import get_fusion_engine
        eng = get_fusion_engine()
        ev = eng.ingest(source=source, kind=kind,
                        payload=dict(payload or {}), severity=severity)
        return ev.event_id
    except Exception:
        return None


def fusion_snapshot(window_s: float = 30.0) -> Dict[str, Any]:
    """Snapshot contextual (Bloque 83) para decidir si refactorizar es seguro."""
    try:
        from backend.fusion.sensory import get_fusion_engine
        return get_fusion_engine().snapshot(window_s=window_s).to_dict()
    except Exception as exc:
        return {"state": "unknown", "error": str(exc), "offline_only": True}


def master_probe() -> Dict[str, Any]:
    """Probe del orquestador maestro (Bloque 100) con el motor de refactoring."""
    try:
        from backend.core.aura_master_runtime import get_master_runtime
        rt = get_master_runtime()
        return {"master_state": rt.status().get("state"),
                "offline_only": True}
    except Exception as exc:
        return {"master_state": "unknown", "error": str(exc),
                "offline_only": True}


__all__ = ["governor_gate", "emit_fusion", "fusion_snapshot", "master_probe"]
