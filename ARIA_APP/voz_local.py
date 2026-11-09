# -*- coding: utf-8 -*-
"""ARIA - Voz local con pyttsx3 (SAPI de Windows, offline, sin deps nuevas).

pyttsx3 ya esta instalado y usa las voces del sistema. Cero HTTP, cero servidores.
Habla en un hilo aparte para no congelar la UI. Solo se habla una frase a la vez
(lock), y cualquier fallo de TTS es silencioso: la voz nunca tumba ARIA.
"""
import threading

_lock = threading.Lock()
_engine = None


def disponible():
    try:
        import pyttsx3  # noqa: F401
        return True
    except Exception:
        return False


def _engine_local():
    global _engine
    if _engine is not None:
        return _engine
    import pyttsx3
    e = pyttsx3.init()
    try:
        voces = e.getProperty("voices") or []
        for v in voces:
            vid = (getattr(v, "id", "") or "").upper()
            if "ES" in vid or "SPANISH" in vid:
                e.setProperty("voice", v.id)
                break
    except Exception:
        pass
    try:
        e.setProperty("rate", 175)
    except Exception:
        pass
    _engine = e
    return e


def hablar(texto):
    """Habla `texto` en un hilo daemon. Devuelve True si se encolo, False si no."""
    texto = (texto or "").strip()
    if not texto or not disponible():
        return False

    def _run():
        with _lock:
            try:
                e = _engine_local()
                e.say(texto)
                e.runAndWait()
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()
    return True
