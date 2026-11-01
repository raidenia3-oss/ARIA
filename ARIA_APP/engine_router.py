# -*- coding: utf-8 -*-
"""ARIA - Router de motor: decide QUE cerebro atiende cada tarea, manteniendo
memoria y skills constantes (idea tomada de Cindy, pero local y sin su stack).

  - tarea simple / charla / snippet corto  -> 'local'  (llama.cpp, rapido, offline)
  - tarea pesada / multi-archivo / proyecto -> 'kilo'   (puente: encola un job,
                                                          fail-closed, no ejecuta solo)

No ejecuta Kilo: solo ENCOLA la orden en kilo_jobs/pending/ para que tu (o el
puente) la corras con aprobacion. Sin servidores, sin red (Regla v2).
"""
import os
import re
import json
import time
import unicodedata

_DIR = os.path.dirname(os.path.abspath(__file__))
_JOBS = os.path.join(_DIR, "kilo_jobs", "pending")

# señales de que la tarea es PESADA (mejor Kilo)
_PESADAS = [
    "app", "aplicacion", "proyecto", "sistema", "backend", "frontend",
    "base de datos", "refactor", "refactoriza", "reescribe", "migra", "migracion",
    "integra", "varios archivos", "multiples archivos", "modulo completo",
    "todo el", "end to end", "pipeline", "arquitectura", "microservicio",
    "crea un bot", "automatiza", "scraper", "dashboard", "api completa",
]
# señales de que es SIMPLE aunque sea codigo (se queda local)
_SIMPLES = ["una funcion", "un snippet", "una linea", "ejemplo corto", "como se hace",
            "que significa", "explica", "corrige esta linea"]


def _norm(s):
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def clasificar(msg):
    """Devuelve {motor, complejidad, razon, senales}."""
    low = _norm(msg)
    senales = [k for k in _PESADAS if k in low]
    simples = [k for k in _SIMPLES if k in low]
    # heuristica: largo y con varias frases tambien pesa
    largo = len(msg) > 320 or msg.count(".") + msg.count("\n") >= 4
    pesada = (len(senales) >= 1 or largo) and not (simples and len(senales) == 0)
    if pesada:
        return {"motor": "kilo", "complejidad": "compleja",
                "razon": "señales pesadas: %s" % (", ".join(senales) or "tarea larga"),
                "senales": senales}
    return {"motor": "local", "complejidad": "simple",
            "razon": "tarea simple; la maneja el cerebro local", "senales": senales}


def crear_job_kilo(prompt, carpeta=None):
    """Encola una orden para Kilo (no la ejecuta). Devuelve la ruta del job."""
    prompt = (prompt or "").strip()
    if not prompt:
        return {"error": "sin prompt"}
    try:
        os.makedirs(_JOBS, exist_ok=True)
    except Exception:
        pass
    jid = "%d" % int(time.time() * 1000)
    job = {"id": jid, "prompt": prompt, "carpeta": carpeta or "",
           "estado": "pendiente", "ts": time.time()}
    ruta = os.path.join(_JOBS, jid + ".json")
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(job, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        return {"error": str(exc)}
    return {"ok": True, "id": jid, "job": ruta}


def enrutar(msg):
    """Clasifica y, si es pesada, encola el job para Kilo. No ejecuta nada."""
    c = clasificar(msg)
    if c["motor"] == "kilo":
        j = crear_job_kilo(msg)
        c["job"] = j
        c["aviso"] = ("Esto es tarea pesada; la encolé para Kilo (%s). "
                      "Ábrela con Kilo cuando quieras (fail-closed, no se ejecuta sola)."
                      % j.get("job", "?")) if j.get("ok") else ("No pude encolar: %s" % j.get("error"))
    return c
