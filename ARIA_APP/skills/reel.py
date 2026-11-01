# -*- coding: utf-8 -*-
"""Skill ARIA: analizar un reel/video (caption + transcripcion + frames)."""
import re

SKILL_ENABLED = True
try:
    import reel_analyzer as _ra
except Exception:
    _ra = None


def match(msg):
    low = msg.lower()
    tiene_link = bool(re.search(r"https?://\S+", msg))
    pide = any(k in low for k in ["analiza este reel", "analiza el reel", "reel", "este video",
                                   "analiza este video", "transcribe", "saca la info"])
    return tiene_link and pide


def run(msg):
    if _ra is None or not _ra.disponible():
        return "Analizador de reels no disponible: instala yt-dlp, opencv y faster-whisper."
    m = re.search(r"https?://\S+", msg)
    if not m:
        return "Pasa el link del reel."
    r = _ra.analizar(m.group(0))
    if not r.get("ok"):
        return r.get("error", "fallo") + ((" (" + r["pista"] + ")") if r.get("pista") else "")
    return ("Listo. %d frames en %s\nCaption: %s\nTranscripcion: %s"
            % (len(r["frames"]), r["carpeta"], r["caption"][:200] or "(ninguno)",
               r["transcripcion"][:400] or "(sin audio)"))
