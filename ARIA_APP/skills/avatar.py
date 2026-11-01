# -*- coding: utf-8 -*-
"""Skill ARIA: que ARIA genere su propia version chibi (sprite-sheet) y la use."""
import threading

SKILL_ENABLED = True
try:
    import chibi_art as _a
except Exception:
    _a = None

_estado = {"corriendo": False, "ultimo": None}


def match(msg):
    low = msg.lower()
    return any(k in low for k in ["crea tu avatar", "genera tu avatar", "genera tu chibi",
                                   "crea tu chibi", "hazte un avatar", "crea tu version chibi",
                                   "crea tu versión chibi", "generate tu avatar"])


def run(msg):
    if _a is None or not _a.disponible():
        return "Para crear mi avatar necesito cv2, numpy y el generador de imagen activos."
    if _estado["corriendo"]:
        return "Ya estoy generando mi avatar, dame un momento."

    def _bg():
        _estado["corriendo"] = True
        try:
            _estado["ultimo"] = _a.generar_sheet()
        except Exception as e:
            _estado["ultimo"] = {"error": str(e)}
        finally:
            _estado["corriendo"] = False

    threading.Thread(target=_bg, daemon=True, name="aria-avatar").start()
    return ("Generando mi version chibi (7 poses, ~1-2 min, necesita internet). "
            "Al terminar queda en assets/chibi/cyberpunk/sheet.png; reinicia el chibi para verme.")
