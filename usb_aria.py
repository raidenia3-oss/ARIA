# -*- coding: utf-8 -*-
"""Analiza unidades USB/extraibles en Windows para planear el uso con ARIA.
Solo LEE: lista unidades removibles, su espacio y contenido de primer nivel.
Uso:  python usb_aria.py
"""
import os, string, ctypes

DRIVE_REMOVABLE = 2

def unidades_removibles():
    out = []
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return out  # no es Windows
    for i, letra in enumerate(string.ascii_uppercase):
        if not (bitmask >> i) & 1:
            continue
        raiz = "%s:\\" % letra
        try:
            tipo = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(raiz))
        except Exception:
            continue
        if tipo == DRIVE_REMOVABLE:
            out.append(raiz)
    return out

def espacio(raiz):
    try:
        free = ctypes.c_ulonglong(0); total = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(
            ctypes.c_wchar_p(raiz), ctypes.byref(free), ctypes.byref(total), None)
        return total.value, free.value
    except Exception:
        return 0, 0

def gb(n): return round(n / (1024**3), 2)

print("=== USB / ANALISIS PARA ARIA ===")
rem = unidades_removibles()
if not rem:
    print("No detecte unidades USB/extraibles. Conecta el USB y reintenta.")
else:
    for raiz in rem:
        tot, free = espacio(raiz)
        print("\nUnidad %s  |  total %s GB  |  libre %s GB" % (raiz, gb(tot), gb(free)))
        try:
            entradas = os.listdir(raiz)
        except Exception as e:
            print("  no pude listar:", e); continue
        print("  contenido (primer nivel):", len(entradas), "items")
        for n in sorted(entradas)[:40]:
            ruta = os.path.join(raiz, n)
            try:
                if os.path.isdir(ruta):
                    print("   [dir ]", n)
                else:
                    print("   [file] %s (%s MB)" % (n, round(os.path.getsize(ruta)/(1024**2), 1)))
            except Exception:
                print("   [?]", n)
print("\n=== FIN === (pegale esta salida a Claude)")
