"""Entrenamiento adaptativo para ARIA: combina QLoRA + layer-streaming + distilacion.
Ajustable a cualquier ambito (dominio). Memoria eficiente: 4GB RAM/VRAM.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
TRAIN_DIR = ROOT / "data" / "entrenamiento_adaptativo"
TRAIN_DIR.mkdir(parents=True, exist_ok=True)


def _cfg_path() -> Path:
    return TRAIN_DIR / "config.json"


def cargar_config() -> Dict[str, Any]:
    p = _cfg_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {
        "modelo_base": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "metodo": "qlora",          # qlora | layer_stream | distill
        "bits": 4,                  # 4 | 8 | 16
        "lora_r": 32,
        "lora_alpha": 64,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
        "stream_layers": True,      # layer streaming (Soup-style)
        "distill_teacher": None,    # modelo maestro para distilacion
        "dominio": "general",       # ajustable: codigo, salud, finanzas, etc.
        "dataset": None,
        "max_seq_len": 512,
        "batch_size": 1,
        "grad_accum": 8,
        "epochs": 3,
        "lr": 2e-4,
    }


def guardar_config(cfg: Dict[str, Any]) -> None:
    _cfg_path().write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def ajustar_dominio(dominio: str, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Ajusta el config para un dominio especifico."""
    cfg = cfg or cargar_config()
    cfg["dominio"] = dominio
    # Heuristicas por dominio
    if dominio in ("codigo", "programacion"):
        cfg["max_seq_len"] = 1024
        cfg["lora_r"] = 64
    elif dominio in ("salud", "medicina"):
        cfg["max_seq_len"] = 512
        cfg["lora_r"] = 32
    elif dominio in ("finanzas", "legal"):
        cfg["max_seq_len"] = 768
        cfg["lora_r"] = 48
    else:
        cfg["max_seq_len"] = 512
        cfg["lora_r"] = 32
    guardar_config(cfg)
    return cfg


def plan_entrenamiento(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Devuelve un plan de entrenamiento combinando las tecnicas."""
    cfg = cfg or cargar_config()
    metodo = cfg.get("metodo", "qlora")
    bits = cfg.get("bits", 4)
    stream = cfg.get("stream_layers", True)
    distill = cfg.get("distill_teacher")

    pasos = []
    pasos.append(f"1. Cargar modelo base {cfg['modelo_base']} en {bits}-bit (bitsandbytes/QLoRA).")
    if stream:
        pasos.append("2. Activar layer-streaming (Soup): base en RAM/NVMe, solo adapter en VRAM.")
    pasos.append(f"3. Aplicar LoRA r={cfg['lora_r']} alpha={cfg['lora_alpha']} sobre {cfg['target_modules']}.")
    if distill:
        pasos.append(f"4. Distilacion: teacher={distill} -> student (KL divergence sobre outputs).")
    pasos.append(f"5. Entrenar dominio='{cfg['dominio']}' epochs={cfg['epochs']} bs={cfg['batch_size']} accum={cfg['grad_accum']}.")
    pasos.append("6. Guardar adapter (LoRA) + merge opcional + exportar GGUF para llama.cpp.")
    pasos.append("7. Evaluar: loss, perplexity, task-specific metric.")
    return {"config": cfg, "pasos": pasos, "memoria_estimada_gb": bits / 8 * 1.1 + 0.5}


def run(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Ejecuta el plan (placeholder: reporta plan, no entrena sin datos)."""
    cfg = cfg or cargar_config()
    if not cfg.get("dataset"):
        return {"status": "sin_dataset", "mensaje": "Falta dataset. Usa ajustar_dominio + set_dataset."}
    plan = plan_entrenamiento(cfg)
    return {"status": "plan_listo", "plan": plan["pasos"], "memoria_gb": plan["memoria_estimada_gb"]}


def set_dataset(path: str, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = cfg or cargar_config()
    cfg["dataset"] = path
    guardar_config(cfg)
    return {"ok": True, "dataset": path}


def status() -> Dict[str, Any]:
    cfg = cargar_config()
    return {"config": cfg, "train_dir": str(TRAIN_DIR), "dataset_ok": bool(cfg.get("dataset"))}
