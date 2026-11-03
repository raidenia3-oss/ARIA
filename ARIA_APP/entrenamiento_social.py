"""entrenamiento_social: genera datos de entrenamiento para ARIA sobre personajes y comunicacion."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "entrenamiento_social"
OUT.mkdir(parents=True, exist_ok=True)


def _ejemplos_personaje(nombre: str, rasgos: List[str], n: int = 20) -> List[Dict[str, str]]:
    out = []
    for i in range(n):
        r = rasgos[i % len(rasgos)]
        out.append({
            "instruccion": f"Responde como {nombre} ante una situacion social.",
            "entrada": f"Situacion {i+1}: alguien te pregunta algo directo.",
            "salida": f"Como {nombre}, uso {r} para manejar la situacion con carisma y sin agresion.",
        })
    return out


def generar_ciclo(cerebro=None, ciclos: int = 5) -> Dict[str, Any]:
    """Genera datos de entrenamiento en ciclos repetidos."""
    personajes = {
        "Patrick Jane": ["observacion", "lectura de microexpresiones", "calma", "humor seco", "empatia estrategica"],
        "Barney Stinson": ["confianza", "humor", "historias", "energia", "carisma"],
    }
    conversacion = [
        "escucha activa", "validacion emocional", "preguntas abiertas",
        "parafraseo", "empatia", "humor ligero", "storytelling",
        "rapport", "registro espejo", "no contradiccion de emociones",
    ]
    vocabulario = [
        "fluidez", "naturalidad", "transiciones suaves", "muletillas minimas",
        "variedad lexica", "tono conversacional", "preguntas de seguimiento",
    ]

    todo: List[Dict[str, str]] = []
    for c in range(ciclos):
        for nom, rasgos in personajes.items():
            todo.extend(_ejemplos_personaje(nom, rasgos, n=10))
        for tema in conversacion:
            todo.append({"instruccion": "Explica la tecnica social.", "entrada": tema,
                         "salida": f"La tecnica '{tema}' consiste en ... (practicar con ejemplos)."})
        for v in vocabulario:
            todo.append({"instruccion": "Mejora la fluidez.", "entrada": v,
                         "salida": f"Practica '{v}' en conversaciones reales para hablar mas natural."})

    out_path = OUT / f"ciclo_{ciclos}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for item in todo:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return {"ciclos": ciclos, "ejemplos": len(todo), "archivo": str(out_path)}


def status() -> Dict[str, Any]:
    return {"archivos": sorted(str(p) for p in OUT.glob("*.jsonl")), "total": len(list(OUT.glob("*.jsonl")))}
