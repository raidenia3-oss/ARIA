# -*- coding: utf-8 -*-
"""ARIA - Migrador de secretos: .env (texto plano) -> boveda cifrada.

Corre UNA vez en tu PC. Te pide la contrasena maestra (no se guarda, no se muestra).
  - crea la boveda si no existe (o la abre si ya existe)
  - mete cada variable del .env en la boveda
  - verifica y BORRA el .env (deja .env.bak por si acaso; borralo tu cuando confirmes)
  - opcional: importa un cookies.txt de Instagram a la boveda

Uso (Git Bash, dentro de ARIA_APP):
  ./.venv/Scripts/python.exe migrar_secretos.py
  ./.venv/Scripts/python.exe migrar_secretos.py --cookies data/reels/cookies.txt
"""
import os
import sys
import getpass

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)

import vault as _vault


def _leer_env(ruta):
    pares = {}
    if not os.path.isfile(ruta):
        return pares
    for ln in open(ruta, encoding="utf-8"):
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        pares[k.strip()] = v.strip().strip('"').strip("'")
    return pares


def main():
    cookies_path = None
    if "--cookies" in sys.argv:
        i = sys.argv.index("--cookies")
        if i + 1 < len(sys.argv):
            cookies_path = sys.argv[i + 1]

    if not _vault.disponible():
        print("ERROR: falta 'cryptography' -> ./.venv/Scripts/python.exe -m pip install cryptography")
        return 1

    v = _vault.Vault()   # data/vault.dat
    master = getpass.getpass("Contrasena maestra de la boveda: ")
    if v.existe():
        r = v.abrir(master)
    else:
        print("No hay boveda; creando una nueva.")
        m2 = getpass.getpass("Repite la contrasena: ")
        if master != m2:
            print("ERROR: las contrasenas no coinciden.")
            return 1
        r = v.crear(master)
    if not r.get("ok"):
        print("ERROR al abrir/crear la boveda:", r.get("error"))
        return 1

    # 1) migrar .env
    env_path = os.path.join(_DIR, ".env")
    pares = _leer_env(env_path)
    migradas = []
    for k, val in pares.items():
        rr = v.set(k, val)
        if rr.get("ok"):
            migradas.append(k)
    print("Migradas a la boveda:", migradas or "(ninguna)")

    # 2) cookies de Instagram (opcional)
    if cookies_path:
        try:
            import reel_analyzer
            rc = reel_analyzer.importar_cookies(v, cookies_path)
            print("Cookies Instagram:", rc.get("ok") and "guardadas" or rc.get("error"))
        except Exception as exc:
            print("Cookies: no se pudo (%s)" % exc)

    # 3) verificar y borrar .env (deja respaldo .env.bak)
    print("Claves en la boveda ahora:", v.listar())
    if migradas and os.path.isfile(env_path):
        bak = env_path + ".bak"
        try:
            os.replace(env_path, bak)
            print("Hecho. El .env se movio a .env.bak (borralo tu cuando confirmes que todo anda).")
        except Exception as exc:
            print("No pude mover el .env:", exc)
    v.cerrar()
    print("Listo. Ahora ARIA debe abrir la boveda al arrancar y llamar exportar_entorno().")
    return 0


if __name__ == "__main__":
    sys.exit(main())
