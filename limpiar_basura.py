# -*- coding: utf-8 -*-
"""Mueve (no borra) los scripts basura de un solo uso de la RAIZ de AURA a _basura/.
Reversible: revisas _basura/ y la borras tu. No toca subcarpetas ni herramientas utiles.
Uso:  .venv\\Scripts\\python limpiar_basura.py   (o: python limpiar_basura.py)
"""
import os, re, shutil

RAIZ = os.path.dirname(os.path.abspath(__file__))
DESTINO = os.path.join(RAIZ, "_basura")

# patrones de scripts one-off de Kilo (solo en la raiz, solo .py)
BASURA = re.compile(
    r"^(add_.+|fix_.+|patch_.+|patch\d+|gen_.+|gen|show\d*|wire_.+|do_patch\d*|"
    r"clean\d*|prepend_stubs|remove_header|integrate_bots|fix2)\.py$", re.I)

# nunca mover estas (herramientas utiles / entradas reales)
EXCLUIR = {"fix_bom.py", "scan_aria.py", "limpiar_basura.py", "backup_aria.py",
           "main.py", "aria.py", "setup.py", "conftest.py"}

movidos = []
try:
    entradas = os.listdir(RAIZ)
except Exception as e:
    print("ERROR:", e); raise SystemExit(1)

for nombre in sorted(entradas):
    ruta = os.path.join(RAIZ, nombre)
    if not os.path.isfile(ruta):
        continue
    if nombre in EXCLUIR or not nombre.endswith(".py"):
        continue
    if not BASURA.match(nombre):
        continue
    os.makedirs(DESTINO, exist_ok=True)
    dest = os.path.join(DESTINO, nombre)
    if os.path.exists(dest):
        dest = os.path.join(DESTINO, "%d_%s" % (int(os.path.getmtime(ruta)), nombre))
    try:
        shutil.move(ruta, dest)
        movidos.append(nombre)
    except Exception as e:
        print("  no pude mover", nombre, ":", e)

print("=== LIMPIEZA ===")
print("movidos a _basura/:", len(movidos))
for m in movidos:
    print("  ->", m)
print("Revisalos en _basura/ y borra la carpeta cuando confirmes. (Reversible.)")
print("=== FIN ===")
