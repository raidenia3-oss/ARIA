# -*- coding: utf-8 -*-
"""Diagnostico de 1 comando. Dice que falta para el chibi / generador de imagen."""
import sys, os, importlib

print("=== DIAGNOSTICO CHIBI / IMAGEN ===")
print("python:", sys.version.split()[0], "|", sys.executable)
print("cwd:", os.getcwd())
print("--- librerias ---")
for mod in ["PyQt5", "cv2", "numpy", "sqlite_vec", "fastembed", "piper"]:
    try:
        m = importlib.import_module(mod)
        print("  OK   ", mod, getattr(m, "__version__", ""))
    except Exception as e:
        print("  FALTA", mod, "->", type(e).__name__)
print("--- modulos de ARIA (se importan?) ---")
# asegurar que ARIA_APP este en el path
here = os.path.dirname(os.path.abspath(__file__))
for cand in (here, os.path.join(here, "ARIA_APP")):
    if os.path.isfile(os.path.join(cand, "chibi.py")):
        sys.path.insert(0, cand); print("  (ARIA_APP en:", cand, ")"); break
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
for mod in ["gen_imagen", "chibi", "chibi_art"]:
    try:
        importlib.import_module(mod); print("  OK   ", mod)
    except Exception as e:
        print("  ERROR", mod, "->", repr(e))
print("=== FIN (pega esto a Claude) ===")
