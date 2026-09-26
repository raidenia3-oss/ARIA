"""BLOQUE 82 - Built-in scope handlers. Cada handler coordina un subsistema
consolidado (B72 RAG, B78 Mesh, B77 Sandbox, B76 Memory, B81 Diagnostics, B79 Master).
100% offline."""
import time
from typing import Any, Dict

from backend.runner.ecosystem import MissionDirective, MissionStep


def _rag_handler(directive: MissionDirective, step: MissionStep, params: Dict[str, Any]) -> Dict[str, Any]:
    from backend.knowledge.rag import get_rag_system
    query = params.get("query") or directive.params.get("query") or "investigacion sobre soberania local"
    rag = get_rag_system()
    res = rag.query(query=query, top_k=params.get("top_k", 5))
    count = len(res.get("results", [])) if isinstance(res, dict) else 0
    return {"type": "rag", "query": query, "results": count, "offline": True}


def _mesh_handler(directive: MissionDirective, step: MissionStep, params: Dict[str, Any]) -> Dict[str, Any]:
    from backend.network_mesh.mesh import MeshNetwork, MeshConfig
    cfg = MeshConfig(node_id=params.get("node_id", "ecosys-node"), secret=params.get("secret", "ecosystem-secret"))
    net = MeshNetwork(cfg)
    net.start()
    time.sleep(0.05)
    status = net.status()
    net.stop()
    return {"type": "mesh", "peers": status.peers_count, "online": status.is_online}


def _sandbox_handler(directive: MissionDirective, step: MissionStep, params: Dict[str, Any]) -> Dict[str, Any]:
    from backend.sandbox.executor import SandboxExecutor
    code = params.get("code", "result = sum(range(100))")
    out = SandboxExecutor().execute(code)
    return {"type": "sandbox", "exit_ok": bool(out.get("ok", False)), "mode": "local_sandbox"}


def _memory_handler(directive: MissionDirective, step: MissionStep, params: Dict[str, Any]) -> Dict[str, Any]:
    from backend.memory.long_term.store import MemoryStore
    msg = params.get("message", f"Mision '{directive.title}' completada")
    store = MemoryStore()
    store.store(msg, category=params.get("category", "mission"))
    return {"type": "memory", "stored": True, "count": len(store.all())}


def _audit_handler(directive: MissionDirective, step: MissionStep, params: Dict[str, Any]) -> Dict[str, Any]:
    from backend.diagnostics.omni import get_omni_auditor
    auditor = get_omni_auditor()
    report = auditor.run_all()
    return {"type": "audit", "verdict": report.get("verdict"), "checks": len(auditor.check_names()), "offline_only": True}


def _master_handler(directive: MissionDirective, step: MissionStep, params: Dict[str, Any]) -> Dict[str, Any]:
    from backend.master_control.master import MasterOrchestrator
    orch = MasterOrchestrator()
    status = orch.status()
    return {"type": "master", "subsystems": status.get("subsystems", {}), "coordinating": bool(status.get("online", False))}


def build_default_handlers() -> Dict[str, Any]:
    return {"rag": _rag_handler, "mesh": _mesh_handler, "sandbox": _sandbox_handler,
            "memory": _memory_handler, "audit": _audit_handler, "master": _master_handler}
