# -*- coding: utf-8 -*-
"""ARIA - Voz local offline con Piper (sin internet tras bajar la voz, sin servidores).

Piper sintetiza en proceso. La voz (modelo .onnx) se baja UNA vez (urllib, salida)
y luego funciona 100% offline. Reproduce con winsound en Windows.
"""
import os
import wave
import urllib.request

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "voz")
_MODELO = os.environ.get("ARIA_VOZ_MODELO", "es_ES-davefx-medium")
_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/"
_voz = None


def disponible():
    try:
        import piper  # noqa
        return True
    except Exception:
        return False


def _ruta(ext):
    return os.path.join(_DIR, _MODELO + ext)


def _asegurar_modelo():
    os.makedirs(_DIR, exist_ok=True)
    for ext in (".onnx", ".onnx.json"):
        destino = _ruta(ext)
        if os.path.isfile(destino) and os.path.getsize(destino) > 0:
            continue
        url = _BASE + _MODELO + ext
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ARIA-Voz/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r, open(destino, "wb") as f:
                f.write(r.read())
        except Exception as exc:
            return "no pude bajar la voz (%s): %s" % (ext, exc)
    return None


def _cargar():
    global _voz
    if _voz is not None:
        return _voz
    from piper import PiperVoice
    _voz = PiperVoice.load(_ruta(".onnx"), _ruta(".onnx.json"))
    return _voz


def hablar(texto, reproducir=True):
    """Sintetiza 'texto' a un wav local y (en Windows) lo reproduce."""
    texto = (texto or "").strip()
    if not texto:
        return {"error": "nada que decir"}
    if not disponible():
        return {"error": "piper no instalado (pip install piper-tts)"}
    err = _asegurar_modelo()
    if err:
        return {"error": err}
    try:
        voz = _cargar()
        salida = os.path.join(_DIR, "aria_voz.wav")
        with wave.open(salida, "wb") as wf:
            voz.synthesize_wav(texto, wf)
    except Exception as exc:
        return {"error": "sintesis fallo: %s" % exc}
    if reproducir and os.name == "nt":
        try:
            import winsound
            winsound.PlaySound(salida, winsound.SND_FILENAME)
        except Exception:
            pass
    return {"ok": True, "wav": salida, "resumen": "Dicho en voz alta."}
