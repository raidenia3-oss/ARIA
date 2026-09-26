"""BLOQUE 103 - Pasos E2E (llamadas directas a motores locales, sin HTTP)."""
from __future__ import annotations

from typing import Any, Callable, Dict


def s_master_launch() -> Dict[str, Any]:
    from backend.core.aura_master_runtime import get_master_runtime
    rep = get_master_runtime().launch()
    return {"state": rep.get("state"), "session": rep.get("session_id")}


def s_governor_gate() -> Dict[str, Any]:
    from backend.refactoring.integration import governor_gate
    g = governor_gate()
    return {"allowed": g.get("allowed"), "decision": g.get("decision")}


def s_fusion_ingest() -> Dict[str, Any]:
    from backend.fusion.sensory import get_fusion_engine
    ev = get_fusion_engine().ingest(source="system", kind="e2e.ping",
                                    payload={"block": 103}, severity="info")
    return {"event_id": ev.event_id}


def s_fusion_context() -> Dict[str, Any]:
    from backend.fusion.sensory import get_fusion_engine
    snap = get_fusion_engine().snapshot(window_s=30.0)
    return {"state": snap.state, "events": snap.event_count}


def s_memory_cognitive() -> Dict[str, Any]:
    from backend.memory.cognitive_graph import get_cognitive_graph
    g = get_cognitive_graph()
    created = g.ingest("e2e probe node", source="e2e103")
    hits = g.search("e2e probe", limit=3)
    first = created[0].node_id if created else "none"
    return {"ok": True, "nodes": len(hits), "ingested": str(first)[:16]}


def s_mesh_publish() -> Dict[str, Any]:
    from backend.network.mesh import get_mesh_orchestrator
    m = get_mesh_orchestrator()
    st = m.engine.status()
    return {"ok": True, "running": st.get("running"),
            "peers": st.get("peers")}


def s_refactor_propose() -> Dict[str, Any]:
    from backend.refactoring.engine import _syntax_ok, get_engine
    ok, err = _syntax_ok("X_E2E103 = 1\n")
    return {"syntax_ok": ok, "err": err,
            "proposals": len(get_engine().list_patches())}


def s_planner_goal() -> Dict[str, Any]:
    from backend.planner.hierarchical import get_planner
    st = get_planner().status()
    return {"ok": True, "goals": str(st)[:200]}


def s_simulation_scenario() -> Dict[str, Any]:
    from backend.simulation.engine import ScenarioConfig, get_engine
    res = get_engine().run_scenario(
        ScenarioConfig(name="e2e103", agents=2, steps=5, seed=7))
    d = res.to_dict()
    return {"scenario": str(d.get("scenario_id", "?"))[:40],
            "status": str(d.get("status", "ok"))[:40]}


def s_federated_round() -> Dict[str, Any]:
    from backend.ai.federated import get_engine, reset_engine
    eng = get_engine()
    rep = eng.start_round(min_nodes=2)
    rid = rep["round_id"]
    key = rep["round_key_b64"].encode("ascii")
    delta = [0.1, 0.2, 0.3, 0.4]
    for node in ("e2e_a", "e2e_b"):
        u = eng.encrypt_update(key, delta, node)
        eng.submit_update(rid, node, u["ciphertext_b64"],
                          u["hmac_sha256"], 1.0)
    agg = eng.aggregate(rid)
    reset_engine()
    return {"aggregated": agg.get("aggregated"),
            "participants": agg.get("participants")}


def s_master_ecosystem() -> Dict[str, Any]:
    from backend.core.aura_master_runtime import get_master_runtime
    probes = get_master_runtime().probe_engines()
    return {"engines_ok": probes.get("engines_ok"),
            "engines_total": probes.get("engines_total")}


STEP_FNS: Dict[str, Callable[[], Dict[str, Any]]] = {
    "master_launch": s_master_launch,
    "governor_gate": s_governor_gate,
    "fusion_ingest": s_fusion_ingest,
    "fusion_context": s_fusion_context,
    "memory_cognitive": s_memory_cognitive,
    "mesh_publish": s_mesh_publish,
    "refactor_propose": s_refactor_propose,
    "planner_goal": s_planner_goal,
    "simulation_scenario": s_simulation_scenario,
    "federated_round": s_federated_round,
    "master_ecosystem": s_master_ecosystem,
}

__all__ = ["STEP_FNS"]
