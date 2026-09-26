# -*- coding: utf-8 -*-
"""FASE POST-100 - Mision autonoma de prueba: planificador jerarquico + auditoria
de refactoring + malla P2P zero-trust + mercado de habilidades. 100% offline.

Uso: .venv/Scripts/python.exe scripts/post100_mission.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.core.aura_master_runtime import get_master_runtime
from backend.planner.hierarchical import HierarchicalGoalDecomposer
from backend.simulation.engine import ScenarioConfig, get_engine as get_sim_engine
from backend.security.identity_engine import get_identity_engine
from backend.marketplace_manager import (
    AppRegistration,
    MarketplaceManager,
    VersionRecord,
)

AUDIT_TARGETS = ["backend/simulation/engine.py", "backend/core/aura_master_runtime.py"]


def mission_plan(refac) -> dict:
    """FASE 3a - Misión autónoma en el planificador jerárquico (Bloque 92)."""
    planner = HierarchicalGoalDecomposer()
    goal = planner.decompose(
        title="Post-100: Auditar y optimizar modulos del backend",
        description="Mision autonomia de largo alcance sobre motores consolidados",
        milestones=[
            {"title": "Auditoria AST de modulos backend"},
            {"title": "Optimizacion de hallazgos de complejidad"},
            {"title": "Validacion de estabilidad del runtime maestro"},
        ],
        priority=1,
    )
    m_ids = [m.milestone_id for m in goal.milestones]
    # Hito 1: auditoria real con el motor de refactoring (Bloque 91)
    findings = []
    for target in AUDIT_TARGETS:
        findings.extend(refac.audit_file(target))
    planner.update_milestone(goal.goal_id, m_ids[0], status=None, progress=100.0)
    # Hito 2: sintesis de propuestas de optimizacion para hallazgos con confianza >= 0.9
    proposals = [f for f in findings if f.confidence >= 0.9]
    planner.update_milestone(goal.goal_id, m_ids[1], progress=50.0 if proposals else 0.0)
    return {"goal": goal.to_dict(), "findings": len(findings),
            "high_confidence": len(proposals)}


def mission_stress() -> dict:
    """FASE 3b - Validacion de carga con el simulador global (Bloque 99)."""
    eng = get_sim_engine()
    res = eng.run_scenario(ScenarioConfig(
        name="post100_mission", agents=32, steps=200, seed=2026,
        faults=[{"type": "p2p_partition", "step": 80, "duration": 6},
                {"type": "agent_saturation", "step": 150, "duration": 4}]))
    return res.to_dict()


def mission_p2p_zero_trust() -> dict:
    """FASE 3c - Descubrimiento de nodo remoto con firma zero-trust (Bloque 90)."""
    eng = get_identity_engine()
    local = eng.register(label="pc-master", role="peer")
    remote = eng.register(label="node-remoto-simulado", role="peer")
    discovery = {"type": "mesh_discovery", "from": local.node_id,
                 "to": remote.node_id, "skills": ["audit", "optimize"]}
    signed = eng.sign(local.node_id, discovery)
    accepted = eng.verify(signed)
    # tampering: payload alterado debe ser rechazado (zero-trust)
    tampered = signed.to_dict()
    tampered.pop("offline_only", None)
    tampered["payload"]["skills"] = ["exfiltrate"]
    rejected = eng.verify(tampered)
    return {"local_node": local.node_id, "remote_node": remote.node_id,
            "signature_valid": accepted, "tamper_rejected": (not rejected)}


def mission_marketplace() -> dict:
    """FASE 3d - Simulacion de intercambio de tareas en el mercado (offline)."""
    mk = MarketplaceManager()
    app = mk.create_app(AppRegistration(
        app_id="skill_aura_audit", name="AURA Skill: Backend Audit",
        description="Empaqueta la auditoria AST como habilidad del enjambre",
        category="skills", developer="aura-local-agent", tags=["audit", "post100"]))
    version = mk.publish_version(VersionRecord(
        version_id="ver_post100_1", app_id=app.app_id, version="1.0.0",
        changelog="Habilidad de auditoria publicada por la mision post-100",
        metadata={"origin": "local-swarm", "offline": True}))
    found = mk.search_apps(query="audit")
    ver = mk.get_versions(app.app_id)
    return {"app_id": app.app_id, "published_version": version.version,
            "search_hits": len(found), "versions": len(ver)}


def run_mission() -> dict:
    rt = get_master_runtime()
    if rt.status()["state"] not in ("ready", "degraded"):
        rt.launch()
    from backend.refactoring.engine import get_engine as get_refac_engine
    refac = get_refac_engine()
    report = {
        "runtime": rt.status(),
        "mission_plan": mission_plan(refac),
        "stress_test": mission_stress(),
        "p2p_zero_trust": mission_p2p_zero_trust(),
        "skill_marketplace": mission_marketplace(),
    }
    report["verdict"] = "MISSION_SUCCESS" if (
        report["p2p_zero_trust"]["signature_valid"]
        and report["p2p_zero_trust"]["tamper_rejected"]
        and report["stress_test"]["status"] == "completed"
    ) else "MISSION_PARTIAL"
    return report


if __name__ == "__main__":
    print(json.dumps(run_mission(), indent=2, ensure_ascii=False))
