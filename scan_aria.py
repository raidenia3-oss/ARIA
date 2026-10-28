# -*- coding: utf-8 -*-
"""Escaner de errores sueltos en todo el arbol AURA.
Uso:  .venv\\Scripts\\python scan_aria.py        (o: python scan_aria.py)
Revisa cada .py: sintaxis, BOM, escapes invalidos, mojibake. Pega la salida a Claude.
"""
import os, ast, io, warnings, sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
SALTAR = {".venv", "node_modules", "__pycache__", ".git", ".git_old", "dist", "build",
          ".mypy_cache", ".pytest_cache", "site-packages", ".kilo", "training_checkpoints"}
MOJI = ["Ã¡", "Ã©", "Ã­", "Ã³", "Ãº", "Ã±", "Â¿", "Â¡", "â€"]

tot = ok = 0
problemas = []

for base, dirs, files in os.walk(RAIZ):
    dirs[:] = [d for d in dirs if d not in SALTAR and not d.startswith(".venv")]
    for f in files:
        if not f.endswith(".py"):
            continue
        ruta = os.path.join(base, f)
        rel = os.path.relpath(ruta, RAIZ)
        tot += 1
        try:
            raw = open(ruta, "rb").read()
        except Exception as e:
            problemas.append(("LEER", rel, str(e))); continue
        bom = raw[:3] == b"\xef\xbb\xbf"
        try:
            texto = raw.decode("utf-8-sig")
        except Exception as e:
            problemas.append(("UTF8", rel, str(e))); continue
        # sintaxis + escapes
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                compile(texto, rel, "exec")
                esc = [str(x.message) for x in w if "escape" in str(x.message)]
            moji = sum(texto.count(m) for m in MOJI)
            if bom:
                problemas.append(("BOM", rel, "empieza con BOM U+FEFF"))
            if esc:
                problemas.append(("ESCAPE", rel, "%d escape(s) invalidos" % len(esc)))
            if moji:
                problemas.append(("MOJIBAKE", rel, "%d caracteres corruptos" % moji))
            if not (bom or esc or moji):
                ok += 1
        except SyntaxError as e:
            problemas.append(("SINTAXIS", rel, "linea %s: %s" % (e.lineno, e.msg)))
        except Exception as e:
            problemas.append(("ERROR", rel, str(e)))

print("=== SCAN AURA ===")
print("archivos .py revisados:", tot, "| limpios:", ok, "| con algo:", len(problemas))
graves = [p for p in problemas if p[0] in ("SINTAXIS", "UTF8", "LEER", "ERROR")]
print("\n--- ERRORES GRAVES (rompen import):", len(graves), "---")
for tipo, rel, det in graves[:80]:
    print("  [%s] %s  ->  %s" % (tipo, rel, det))
otros = [p for p in problemas if p[0] in ("BOM", "ESCAPE", "MOJIBAKE")]
print("\n--- MENORES (BOM/escape/mojibake):", len(otros), "---")
for tipo, rel, det in otros[:80]:
    print("  [%s] %s  ->  %s" % (tipo, rel, det))
if len(problemas) > 160:
    print("\n(...%d mas no mostrados)" % (len(problemas) - 160))
print("\n=== FIN ===")
