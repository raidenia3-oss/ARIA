import math
import random
import time

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import (QColor, QPainter, QRadialGradient, QConicalGradient,
                         QLinearGradient, QPen, QBrush, QPixmap, QFont,
                         QFontDatabase, QFontMetricsF, QImage, QPainterPath)

TEMA = {
    "bg0": "#0b1224",
    "bg1": "#050a16",
    "cyan": "#38bdf8",
    "estados": {
        "reposo": {"a": "#38bdf8", "b": "#818cf8", "glow": 0.60, "spin": 0.12, "pulse": 0.35, "label": "EN REPOSO", "sub": "esperando tu orden"},
        "escuchando": {"a": "#2dd4bf", "b": "#38bdf8", "glow": 0.80, "spin": 0.20, "pulse": 0.90, "label": "ESCUCHANDO", "sub": "te escucho..."},
        "pensando": {"a": "#a78bfa", "b": "#38bdf8", "glow": 0.90, "spin": 0.55, "pulse": 0.50, "label": "PENSANDO", "sub": "procesando tu orden"},
        "hablando": {"a": "#7dd3fc", "b": "#e0f2fe", "glow": 1.00, "spin": 0.25, "pulse": 1.00, "label": "HABLANDO", "sub": "respondiendo"},
        "alerta": {"a": "#fbbf24", "b": "#fb7185", "glow": 0.95, "spin": 0.30, "pulse": 1.20, "label": "ALERTA", "sub": "requiere tu aprobacion"},
    },
}

FUENTE = "DejaVu Sans"


def elegir_fuente():
    global FUENTE
    fams = set(QFontDatabase().families())
    for f in ("Segoe UI Variable", "Segoe UI", "Cascadia Mono", "Inter", "DejaVu Sans"):
        if f in fams:
            FUENTE = f
            return


def texto(p, x, y, s, px=12, color="#cbd5e1", bold=False, esp=0.0, alinear="l", alpha=255):
    f = QFont(FUENTE)
    f.setPixelSize(px)
    f.setBold(bold)
    if esp:
        f.setLetterSpacing(QFont.AbsoluteSpacing, esp)
    c = QColor(color)
    c.setAlpha(alpha)
    p.setFont(f)
    p.setPen(c)
    w = QFontMetricsF(f).horizontalAdvance(s)
    if alinear == "c":
        x -= w / 2
    elif alinear == "r":
        x -= w
    p.drawText(QPointF(x, y), s)
    return w


class Nucleo:
    def __init__(self, n=520, seed=7):
        rnd = random.Random(seed)
        g = math.pi * (3 - math.sqrt(5))
        self.pts = []
        for i in range(n):
            y = 1 - 2 * (i + 0.5) / n
            r = math.sqrt(max(0.0, 1 - y * y))
            j = 0.97 + rnd.random() * 0.06
            self.pts.append((math.cos(g * i) * r * j, y * j, math.sin(g * i) * r * j, rnd.random()))
        self._cache = {}

    def sprite(self, color, size=256):
        key = (QColor(color).rgba(), size)
        pm = self._cache.get(key)
        if pm is None:
            pm = QPixmap(size, size)
            pm.fill(Qt.transparent)
            q = QPainter(pm)
            q.setRenderHint(QPainter.Antialiasing)
            g = QRadialGradient(size / 2, size / 2, size / 2)
            for pos, a in ((0.0, 255), (0.16, 170), (0.45, 48), (1.0, 0)):
                c = QColor(color)
                c.setAlpha(a)
                g.setColorAt(pos, c)
            q.setPen(Qt.NoPen)
            q.setBrush(QBrush(g))
            q.drawEllipse(0, 0, size, size)
            q.end()
            self._cache[key] = pm
        return pm

    def _blit(self, p, pm, cx, cy, rad, op):
        p.setOpacity(op)
        p.drawPixmap(QRectF(cx - rad, cy - rad, 2 * rad, 2 * rad), pm, QRectF(pm.rect()))

    def paint(self, p, rect, t, estado="reposo", nivel=0.0, hud=False, cpu=0.23, ram=0.41):
        st = TEMA["estados"][estado]
        ca, cb = QColor(st["a"]), QColor(st["b"])
        cx, cy = rect.center().x(), rect.center().y()
        R = min(rect.width(), rect.height()) * (0.185 if hud else 0.34)
        pulso = 1 + 0.035 * st["pulse"] * math.sin(t * 2.2) + 0.08 * nivel
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        sa, sb, sw = self.sprite(ca), self.sprite(cb), self.sprite("#ffffff", 128)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        self._blit(p, sa, cx, cy, R * 2.9 * pulso, 0.42 * st["glow"])
        self._blit(p, sb, cx, cy, R * 1.9 * pulso, 0.20 * st["glow"])
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        if hud:
            pass
        ry, rx = t * st["spin"], 0.42 + 0.10 * math.sin(t * 0.3)
        cyr, syr, cxr, sxr = math.cos(ry), math.sin(ry), math.cos(rx), math.sin(rx)
        items = []
        for x, y, z, k in self.pts:
            x1 = x * cyr + z * syr
            z1 = -x * syr + z * cyr
            y1 = y * cxr - z1 * sxr
            z2 = y * sxr + z1 * cxr
            items.append((z2, x1, y1, k))
        items.sort()
        Rr = R * 1.03 * pulso
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        trasera = [it for it in items if it[0] < 0]
        frontal = [it for it in items if it[0] >= 0]
        self._particulas(p, trasera, cx, cy, Rr, t, sa, sb, 0.55)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        g = QRadialGradient(cx - R * 0.25, cy - R * 0.30, R * 1.15)
        g.setColorAt(0.0, QColor(20, 36, 70, 235))
        g.setColorAt(1.0, QColor(4, 9, 20, 248))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), R * 0.94, R * 0.94)
        path = QPainterPath()
        path.addEllipse(QPointF(cx, cy), R * 0.93, R * 0.93)
        p.setClipPath(path)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        for i in range(4):
            ang = t * (0.55 + 0.22 * i) + i * 1.9
            ox, oy = math.cos(ang) * R * 0.22, math.sin(ang * 1.25) * R * 0.22
            rad = R * (0.62 + 0.08 * math.sin(t * 1.6 + i)) * pulso
            self._blit(p, sa if i % 2 == 0 else sb, cx + ox, cy + oy, rad, 0.50 * st["glow"])
        self._blit(p, self.sprite("#ffffff", 128), cx, cy, R * 0.34 * (1 + 0.10 * nivel), 0.95)
        p.setClipping(False)
        rim = QRadialGradient(cx, cy, R)
        c0 = QColor(ca)
        c0.setAlpha(0)
        c1 = QColor(cb)
        c1.setAlpha(190)
        rim.setColorAt(0.0, c0)
        rim.setColorAt(0.80, c0)
        rim.setColorAt(0.965, c1)
        rim.setColorAt(1.0, c0)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(rim))
        p.drawEllipse(QPointF(cx, cy), R, R)
        self._particulas(p, frontal, cx, cy, Rr, t, sa, sb, 1.0)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)

    def _particulas(self, p, lista, cx, cy, Rr, t, sa, sb, fuerza):
        for z2, x1, y1, k in lista:
            prof = (z2 + 1) / 2
            s = 2.2 + 5.2 * prof
            op = (0.14 + 0.86 * prof) * (0.72 + 0.28 * math.sin(t * 2.0 + k * 50)) * fuerza
            self._blit(p, sb if prof > 0.62 else sa, cx + x1 * Rr, cy + y1 * Rr, s, min(1.0, op * 0.95))
