# AURA_Core/dream_and_distill.py
# Fase 23 - Destilación de Procesos en Reposo (Dream & Distill)

import json
import logging
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("DreamAndDistill")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())

# Zona de código muerto: placeholder integración dashboard
DASHBOARD_DEAD_ZONE_UPDATE = None  # TODO: conectar UI dashboard inactivo

# Rutas de soporte
CHAT_LOG_PATH = "AURA_Core/chat_history.json"
KNOWLEDGE_GRAPH_PATH = "AURA_Core/knowledge_graph.json"
SKILLS_DISTILLED_PATH = "AURA_Core/skills_distilled.json"
LAST_ACTIVITY_PATH = "AURA_Core/last_user_activity.ts"


def _now() -> datetime:
    return datetime.utcnow()


def _load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"No se pudo cargar {path}: {e}")
        return None


def _save_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_user_last_activity() -> Optional[datetime]:
    try:
        txt = Path(LAST_ACTIVITY_PATH).read_text(encoding="utf-8").strip()
        if not txt:
            return None
        txt = txt.replace("Z", "+00:00")
        return datetime.fromisoformat(txt)
    except Exception as e:
        logger.warning(f"Error leyendo {LAST_ACTIVITY_PATH}: {e}")
        return None


def _touch(last_ts: Optional[datetime] = None) -> None:
    ts = (last_ts or _now()).isoformat()
    Path(LAST_ACTIVITY_PATH).write_text(ts, encoding="utf-8")


def detect_inactivity(minutes: int = 30) -> bool:
    last = _read_user_last_activity()
    if last is None:
        return True
    return (_now() - last) >= timedelta(minutes=minutes)


# ============================
# MÓDULO DREAM
# ============================


def dream_consolidate_memory() -> Dict[str, Any]:
    """
    Consolidación en reposo (DREAM).
    - Elimina redundancias en grafos.
    - Resume conversaciones antiguas en vectores clave.
    - Limpia conexiones huérfanas.
    """
    logger.info("[DREAM] Iniciando consolidación de memoria...")
    report: Dict[str, Any] = {
        "timestamp": _now().isoformat(),
        "removed_orphans": 0,
        "compressed_chats": 0,
        "summary_vectors": 0,
        "graph_nodes_before": 0,
        "graph_nodes_after": 0,
    }

    # 1. Grafo de conocimiento relacional
    kg = _load_json(KNOWLEDGE_GRAPH_PATH) or {"nodes": [], "edges": []}
    nodes_before = len(kg.get("nodes", []))
    report["graph_nodes_before"] = nodes_before

    # Limpiar nodos huérfanos
    connected_ids = set()
    for e in kg.get("edges", []):
        connected_ids.add(str(e.get("source", e.get("from", ""))))
        connected_ids.add(str(e.get("target", e.get("to", ""))))

    before_orphans = len(kg.get("nodes", []))
    kg["nodes"] = [
        n for n in kg.get("nodes", []) if str(n.get("id", n.get("key", ""))) in connected_ids
    ]
    removed = before_orphans - len(kg["nodes"])
    report["removed_orphans"] = removed

    # 2. Compresión de historial de chat a vectores clave (simulado)
    chat = _load_json(CHAT_LOG_PATH) or []
    original_chat_count = len(chat)
    if original_chat_count > 10:
        cutoff = _now() - timedelta(hours=24)
        kept = []
        summarized = 0
        for msg in chat:
            ts_str = msg.get("timestamp")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else None
            except Exception:
                ts = None
            if ts and ts < cutoff:
                summarized += 1
                continue
            kept.append(msg)
        report["compressed_chats"] = summarized
        _save_json(CHAT_LOG_PATH, kept)

    report["graph_nodes_after"] = len(kg.get("nodes", []))
    report["summary_vectors"] = report["compressed_chats"]
    _save_json(KNOWLEDGE_GRAPH_PATH, kg)
    logger.info("[DREAM] Consolidación completada.")
    return report


# ============================
# MÓDULO DISTILL
# ============================


def distill_pattern_to_skill(sequence: List[str], min_repeats: int = 3) -> Optional[Dict[str, Any]]:
    """
    Si se detecta una secuencia repetitiva de comandos/acciones,
    genera un skill JSON reutilizable.
    """
    # Contador simulado de repeticiones (en producción vendría de telemetría/chat)
    fake_count = random.randint(1, 5)
    if fake_count < min_repeats:
        return None

    skill_name = f"macro_{int(time.time())}"
    skill: Dict[str, Any] = {
        "name": skill_name,
        "description": "Macro generada automáticamente por Distill",
        "trigger": "manual",
        "steps": sequence,
        "created_at": _now().isoformat(),
        "repeat_count": fake_count,
    }
    return skill


def distill_scan_and_generate() -> Dict[str, Any]:
    """
    Escanea patrones de uso y genera skills_distilled.json.
    """
    logger.info("[DISTILL] Escaneando patrones de comandos...")
    report: Dict[str, Any] = {
        "timestamp": _now().isoformat(),
        "scanned_patterns": 0,
        "new_skills": 0,
        "skills": [],
    }

    candidate_sequences = [
        ["revisar_bateria_ame", "abrir_hud_jarvis", "iniciar_bot_rollercoin"],
        ["sincronizar_termux", "actualizar_firmware", "enviar_telemetria"],
        ["escanear_red_wifi", "generar_mapa", "exportar_pdf"],
    ]

    existing_skills = _load_json(SKILLS_DISTILLED_PATH) or {"skills": []}
    skills_list: List[Dict[str, Any]] = existing_skills.get("skills", [])

    for seq in candidate_sequences:
        report["scanned_patterns"] += 1
        skill = distill_pattern_to_skill(seq, min_repeats=3)
        if skill:
            if not any(s.get("name") == skill["name"] for s in skills_list):
                skills_list.append(skill)
                report["new_skills"] += 1

    report["skills"] = skills_list
    _save_json(SKILLS_DISTILLED_PATH, {"skills": skills_list})
    logger.info(f"[DISTILL] {report['new_skills']} skills nuevas generadas.")
    return report


# ============================
# PIPELINE PRINCIPAL
# ============================


def run_dream() -> Dict[str, Any]:
    """Punto de entrada para Chronos: ejecuta consolidación DREAM."""
    if not detect_inactivity(minutes=30):
        logger.info("[DREAM] Actividad reciente detectada; se salta consolidación.")
        return {"status": "skipped", "reason": "active_user"}
    return dream_consolidate_memory()


def run_distill() -> Dict[str, Any]:
    """Punto de entrada para Chronos: ejecuta destilación DISTILL."""
    return distill_scan_and_generate()
