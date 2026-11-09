# -*- coding: utf-8 -*-
"""ARIA - taller retro (ideas robadas de ascii-magic.com).

Convierte imagenes a arte ASCII, aplica dithering con paletas retro (Game Boy,
PICO-8, C64, fosforo verde) y exporta el resultado a PNG/TXT.

Solo PyQt5 + stdlib (Regla v2): sin HTTP, sin servidores, sin dependencias nuevas.

Uso directo:
    import retro_ascii as R
    txt = R.imagen_a_ascii("foto.jpg", ancho=90)
    R.render_ascii_png(txt, "arte.png")
    R.dither("foto.jpg", paleta="gameboy", escala=0.5).save("retro.png")
"""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPixmap

# Rampa de densidad: indice 0 = oscuro (denso), ultimo = claro (espacio)
RAMPA = "@%#*+=-:. "

PALETAS = {
    "gameboy": [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)],
    "pico8": [(0, 0, 0), (29, 43, 83), (126, 37, 83), (0, 135, 81),
              (171, 82, 54), (95, 87, 79), (194, 195, 199), (255, 241, 232),
              (255, 0, 77), (255, 163, 0), (255, 236, 39), (0, 228, 54),
              (41, 173, 255), (131, 118, 156), (255, 119, 168), (255, 204, 170)],
    "c64": [(0, 0, 0), (255, 255, 255), (136, 57, 50), (103, 182, 189),
            (139, 63, 150), (85, 160, 73), (64, 49, 141), (191, 206, 114),
            (139, 84, 41), (87, 66, 0), (184, 105, 98), (80, 80, 80),
            (120, 120, 120), (148, 224, 137), (120, 105, 196), (159, 159, 159)],
    "verde": [(0, 0, 0), (0, 70, 25), (0, 150, 60), (60, 255, 140), (200, 255, 220)],
    "ambar": [(10, 6, 0), (60, 35, 0), (140, 85, 0), (235, 165, 20), (255, 230, 150)],
    "bn": [(0, 0, 0), (255, 255, 255)],
}


def _abrir(ruta, escala=1.0):
    img = QImage(str(ruta))
    if img.isNull():
        raise ValueError("no pude abrir la imagen: %s" % ruta)
    if escala and escala != 1.0:
        img = img.scaled(max(1, int(img.width() * escala)),
                         max(1, int(img.height() * escala)),
                         Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return img.convertToFormat(QImage.Format_RGB32)


def imagen_a_ascii(ruta, ancho=90, rampa=RAMPA, recortar=True):
    """Foto -> arte ASCII. `ancho` en caracteres (40..200)."""
    ancho = max(20, min(200, int(ancho)))
    img = _abrir(ruta)
    alto = max(1, int(ancho * img.height() / float(img.width()) * 0.5))
    img = img.scaled(ancho, alto, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    n = len(rampa) - 1
    lineas = []
    for y in range(img.height()):
        fila = []
        for x in range(img.width()):
            c = img.pixel(x, y)
            r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
            lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
            fila.append(rampa[min(n, int(lum * n))])
        lineas.append(("".join(fila).rstrip()) if recortar else "".join(fila))
    return "\n".join(lineas)


def render_ascii_png(texto, ruta, color=(120, 255, 150), fondo=(2, 6, 4), px=8):
    """Dibuja el ASCII como imagen (fosforo sobre negro). Sirve de wallpaper."""
    if not texto:
        raise ValueError("texto vacio")
    lineas = texto.splitlines()
    f = QFont("Consolas"); f.setPixelSize(px); f.setBold(True)
    fm = QFontMetricsF(f)
    cw, ch = fm.horizontalAdvance("M"), fm.height()
    ancho = max(1, int(max(len(l) for l in lineas) * cw) + 2 * px)
    alto = max(1, int(len(lineas) * ch) + 2 * px)
    pm = QPixmap(ancho, alto); pm.fill(QColor(*fondo))
    p = QPainter(pm); p.setFont(f); p.setPen(QColor(*color))
    y = px + fm.ascent()
    for l in lineas:
        p.drawText(px, int(y), l)
        y += ch
    p.end()
    if ruta:
        pm.save(str(ruta))
    return pm


def _cercano(r, g, b, pal):
    mejor, bd = pal[0], 1e18
    for pr, pg, pb in pal:
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < bd:
            bd, mejor = d, (pr, pg, pb)
    return mejor


def dither(ruta, paleta="gameboy", escala=1.0):
    """Dither Floyd-Steinberg contra la paleta elegida. Devuelve QImage."""
    pal = PALETAS.get(str(paleta).lower()) or PALETAS["gameboy"]
    img = _abrir(ruta, escala)
    W, H = img.width(), img.height()
    filas = []
    for y in range(H):
        fila = []
        for x in range(W):
            c = img.pixel(x, y)
            fila.append([float((c >> 16) & 255), float((c >> 8) & 255), float(c & 255)])
        filas.append(fila)
    salida = bytearray(W * H * 3)
    for y in range(H):
        for x in range(W):
            r, g, b = filas[y][x]
            pr, pg, pb = _cercano(r, g, b, pal)
            filas[y][x] = (pr, pg, pb)
            er, eg, eb = r - pr, g - pg, b - pb
            for dx, dy, f in ((1, 0, 0.4375), (-1, 1, 0.1875), (0, 1, 0.3125), (1, 1, 0.0625)):
                xx, yy = x + dx, y + dy
                if 0 <= xx < W and yy < H:
                    t = filas[yy][xx]
                    if isinstance(t, list):
                        t[0] += er * f; t[1] += eg * f; t[2] += eb * f
            i = (y * W + x) * 3
            salida[i] = pr; salida[i + 1] = pg; salida[i + 2] = pb
    return QImage(bytes(salida), W, H, W * 3, QImage.Format_RGB888).copy()


def paletas():
    return sorted(PALETAS.keys())
