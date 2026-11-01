# -*- coding: utf-8 -*-
"""Verificacion de integracion: native_core + 3 capas de memoria + guard."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARIA_APP = ROOT / "ARIA_APP"
sys.path.insert(0, str(ARIA_APP))
sys.path.insert(0, str(ROOT))

import native_core  # noqa: E402

out = {}

ai = native_core.NativeAIProvider()
logic = native_core.NativeLogicEngine(ai)
out["skills_total"] = len(logic._skills)

# Capa Mnemosyne
r = logic.process("skill", {"skill": "mnemosyne_add", "params": {
    "content": "el usuario quiere ARIA con panel de control en tiempo real",
    "role": "user", "importance": 0.9, "tags": ["ui"]}})
out["mnemosyne_add"] = r

r = logic.process("skill", {"skill": "mnemosyne_search", "params": {"query": "tiempo real"}})
out["mnemosyne_search"] = {"status": r["status"], "hits": len(r["results"])}

# Capa Hindsight
r = logic.process("skill", {"skill": "hindsight_reflect", "params": {
    "session_id": "verificacion",
    "conversation": "El usuario pidio un panel de control en tiempo real para ARIA."}})
out["hindsight_reflect"] = {
    "status": r["status"], "summary": r["summary"][:120],
    "preferences": r["preferences_learned"], "patterns": r["patterns_identified"]}

r = logic.process("skill", {"skill": "hindsight_insights", "params": {}})
out["hindsight_insights"] = {"status": r["status"], "count": r["count"]}

r = logic.process("skill", {"skill": "hindsight_context", "params": {"query": "panel de control"}})
out["hindsight_context"] = {"status": r["status"], "hits": len(r["context"])}

# Capa Wiki
r = logic.process("skill", {"skill": "wiki_write", "params": {
    "title": "Verificacion de capas",
    "content": "Mnemosyne, Hindsight y Wiki funcionan. Ver [[Mnemosyne]].",
    "tags": ["prueba", "memoria"]}})
out["wiki_write"] = {"status": r["status"], "note_id": r["note_id"]}

r = logic.process("skill", {"skill": "wiki_search", "params": {"query": "capas"}})
out["wiki_search"] = {"status": r["status"], "hits": len(r["results"])}

r = logic.process("skill", {"skill": "wiki_read", "params": {"title": "Verificacion de capas"}})
out["wiki_read"] = {"status": r["status"], "tags": r.get("tags")}

# Estado de las 3 capas
r = logic.process("skill", {"skill": "memory_layers", "params": {}})
out["memory_layers"] = {
    "mnemosyne": r["mnemosyne"]["entries"],
    "hindsight": r["hindsight"]["total_insights"],
    "wiki": r["obsidian_wiki"]["total_notes"],
    "capas": r["capas"],
}

# Guard de procesos
r = logic.process("skill", {"skill": "process_guard_status", "params": {}})
out["process_guard_status"] = {
    "policy": r["policy"]["policy"],
    "name_kill_allowed": r["policy"]["name_kill_allowed"],
    "protected_sample": r["snapshot"]["protected_processes"][:5],
}

r = logic.process("skill", {"skill": "process_list", "params": {"name": "chrome", "limit": 5}})
out["process_list_chrome"] = {
    "count": r["count"],
    "processes": [{"pid": p["pid"], "name": p["name"], "terminable": p["terminable"],
                   "code": p["code"]} for p in r["processes"]],
}

# Intento de terminar un proceso ajeno (debe ser denegado)
r = logic.process("skill", {"skill": "process_terminate", "params": {"pid": 4}})
out["process_terminate_system"] = {"status": r["status"], "code": r.get("code"),
                                   "reason": r.get("reason", "")[:110]}

# Sin PID: debe exigir PID explicito
r = logic.process("skill", {"skill": "process_terminate", "params": {}})
out["process_terminate_no_pid"] = {"status": r["status"], "code": r.get("code")}

Path(ROOT / "_verif_capas.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("WROTE _verif_capas.json")
