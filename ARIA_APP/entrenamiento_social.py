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


TRUCOS_PATRICK_JANE = [
    "observacion de microexpresiones para detectar mentiras",
    "calma y paciencia para que el otro se delate",
    "humor seco para desarmar tension",
    "empatia estrategica: entender antes de influir",
    "lectura de lenguaje corporal y gestos",
    "preguntas indirectas para revelar informacion",
    "silencio estrategico para que el otro hable",
    "no contradiccion directa: guiar sin forzar",
    "reconocer emociones para construir rapport",
    "nunca usar violencia: solo inteligencia y carisma",
]

TRUCOS_BARNEY_STINSON = [
    "confianza extrema como herramienta de atraccion",
    "historias dramaticas para captar atencion",
    "energia alta y positiva en interacciones",
    "carisma y humor como puerta de entrada",
    "marco de juego: convertir situaciones en divertidas",
    "no desesperacion: siempre parecer tener opciones",
    "apariencia cuidada y postura dominante",
    "escucha para encontrar puntos en comun",
    "complimentar genuinamente sin adulacion",
    "respetar limites: si dice no, aceptar y seguir",
]

LIMITE_DURO = [
    "nunca manipular para danar a alguien",
    "nunca mentir para obtener favores sexuales",
    "nunca insistir despues de un no",
    "nunca usar informacion intima como arma",
    "nunca fingir acuerdo en hechos (empatia != adulacion)",
]


def _ejemplos_trucos(n: int = 10) -> List[Dict[str, str]]:
    out = []
    for t in TRUCOS_PATRICK_JANE + TRUCOS_BARNEY_STINSON:
        out.append({
            "instruccion": "Ensenar como usar esta tecnica social de forma etica.",
            "entrada": t,
            "salida": "Tecnica: " + t + ". Aplicar con respeto, sin manipulacion danina. Limite: " + LIMITE_DURO[0] + ".",
        })
    for l in LIMITE_DURO:
        out.append({
            "instruccion": "Explicar un limite duro que NUNCA se cruza.",
            "entrada": l,
            "salida": "Limite duro: " + l + ". ARIA nunca ensena ni aplica esto.",
        })
    return out[:n]


def simular_conversacion_desconocida(cerebro=None, turnos: int = 6) -> Dict[str, Any]:
    """Simula conversar con una desconocida desde cero, usando trucos de ambos."""
    apertura = "Hola, no te conozco pero me llamo la atencion tu estilo. Soy Daniel."
    historial = [apertura]
    respuestas = []
    for i in range(turnos):
        msg = f"Turno {i+1}: la desconocida responde algo."
        if cerebro is not None:
            try:
                r = cerebro.chat(msg + " " + " ".join(historial[-2:])).get("response", "")
                respuestas.append(r)
                historial.append(r)
            except Exception as e:
                respuestas.append(f"error: {e}")
        else:
            respuestas.append(f"[simulado] respuesta {i+1}")
    return {"apertura": apertura, "turnos": turnos, "respuestas": respuestas, "historial": historial}


def generar_ciclo(cerebro=None, ciclos: int = 5) -> Dict[str, Any]:
    """Genera datos de entrenamiento en ciclos repetidos (multiplicado)."""
    todo: List[Dict[str, str]] = []
    todo.extend(_ejemplos_trucos(20))
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
    for c in range(ciclos * 3):  # multiplicar repeticion
        for nom, rasgos in personajes.items():
            todo.extend(_ejemplos_personaje(nom, rasgos, n=10))
        for tema in conversacion:
            todo.append({"instruccion": "Explica la tecnica social.", "entrada": tema,
                         "salida": "La tecnica '" + tema + "' consiste en ... (practicar con ejemplos)."})
        for v in vocabulario:
            todo.append({"instruccion": "Mejora la fluidez.", "entrada": v,
                         "salida": "Practica '" + v + "' en conversaciones reales para hablar mas natural."})

    out_path = OUT / ("ciclo_" + str(ciclos * 3) + ".jsonl")
    with out_path.open("w", encoding="utf-8") as f:
        for item in todo:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return {"ciclos": ciclos * 3, "ejemplos": len(todo), "archivo": str(out_path)}
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
    todo.extend(_ejemplos_trucos(20))
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
