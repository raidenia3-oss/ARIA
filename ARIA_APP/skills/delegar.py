# -*- coding: utf-8 -*-
"""Skill ARIA: delegar una tarea pesada a Kilo (la encola, fail-closed)."""
import re

SKILL_ENABLED = True
try:
    import engine_router as _r
except Exception:
    _r = None


def match(msg):
    low = msg.lower()
    return any(k in low for k in ["delega a kilo", "delega esto a kilo", "manda a kilo",
                                   "pasa a kilo", "pasale a kilo", "encola para kilo",
                                   "tarea pesada para kilo"])


def run(msg):
    if _r is None:
        return "Router no disponible."
    tarea = re.sub(r".*?kilo\s*:?\s*", "", msg, count=1, flags=re.I).strip() or msg
    j = _r.crear_job_kilo(tarea)
    if j.get("ok"):
        return ("Encolé la tarea para Kilo en %s. Ábrela con Kilo (kilo run --auto) "
                "cuando quieras — no se ejecuta sola." % j["job"])
    return "No pude encolar: %s" % j.get("error")
