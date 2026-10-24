import math, random, time
from PyQt5.QtCore import Qt, QPointF, QRectF, QLineF
from PyQt5.QtGui import (QColor, QPainter, QRadialGradient, QConicalGradient,
                         QLinearGradient, QPen, QBrush, QPixmap, QFont,
                         QFontDatabase, QFontMetricsF, QImage, QPainterPath)
from PyQt5.QtWidgets import QApplication

TEMA = {
    "bg0": "#0b1224",
    "bg1": "#050a16",
    "cyan": "#38bdf8",
    "estados": {
        "reposo":     {"a": "#38bdf8", "b": "#818cf8", "glow": 0.60, "spin": 0.12, "pulse": 0.35, "label": "EN REPOSO", "sub": "esperando tu orden"},
        "escuchando": {"a": "#2dd4bf", "b": "#38bdf8", "glow": 0.80, "spin": 0.20, "pulse": 0.90, "label": "ESCUCHANDO", "sub": "te escucho..."},
        "pensando":   {"a": "#a78bfa", "b": "#38bdf8", "glow": 0.90, "spin": 0.55, "pulse": 0.50, "label": "PENSANDO", "sub": "procesando tu orden"},
        "hablando":   {"a": "#7dd3fc", "b": "#e0f2fe", "glow": 1.00, "spin": 0.25, "pulse": 1.00, "label": "HABLANDO", "sub": "respondiendo"},
        "alerta":     {"a": "#fbbf24", "b": "#fb7185", "glow": 0.95, "spin": 0.30, "pulse": 1.20, "label": "ALERTA", "sub": "requiere tu aprobacion"},
    },
}
ESTADOS = TEMA["estados"]
BG0, BG1 = TEMA["bg0"], TEMA["bg1"]
CYAN = TEMA["cyan"]
FUENTE = "DejaVu Sans"

def elegir_fuente():
    global FUENTE
    fams = set(QFontDatabase().families())
    for f in ("Segoe UI Variable", "Segoe UI", "Cascadia Mono", "Inter", "DejaVu Sans"):
        if f in fams:
            FUENTE = f
            return

def texto(p, x, y, s, px=12, color="#cbd5e1", bold=False, esp=0.0, alinear="l", alpha=255):
    f = QFont(FUENTE); f.setPixelSize(px); f.setBold(bold)
    if esp:
        f.setLetterSpacing(QFont.AbsoluteSpacing, esp)
    c = QColor(color); c.setAlpha(alpha)
    p.setFont(f); p.setPen(c)
    w = QFontMetricsF(f).horizontalAdvance(s)
    if alinear == "c": x -= w / 2
    elif alinear == "r": x -= w
    p.drawText(QPointF(x, y), s)
    return w

class Nucleo:
    CAL = {"alta":  dict(n=520, hud=True,  anillos=3, onda=True,  blobs=4),
           "media": dict(n=300, hud=False, anillos=2, onda=True,  blobs=3),
           "baja":  dict(n=140, hud=False, anillos=0, onda=False, blobs=2)}
    ORDEN = ("baja", "media", "alta")
    ANILLOS = ((1.28, 2.6, 1.00, -18, 0.34, 0), (1.42, 1.7, -0.70, 26, 0.30, 1), (1.56, 1.2, 0.45, 72, 0.38, 0))
    NB = 6

    def __init__(self, n=520, seed=7):
        rnd = random.Random(seed)
        g = math.pi * (3 - math.sqrt(5))
        self.pts = []
        for i in range(n):
            y = 1 - 2 * (i + 0.5) / n
            r = math.sqrt(max(0.0, 1 - y * y))
            j = 0.97 + rnd.random() * 0.06
            self.pts.append((math.cos(g * i) * r * j, y * j, math.sin(g * i) * r * j, rnd.random()))
        self._spr, self._c2, self._ms = {}, {}, []
        self.calidad = "alta"

    def sprite(self, color, size=256):
        key = (QColor(color).rgba(), size)
        pm = self._spr.get(key)
        if pm is None:
            pm = QPixmap(size, size); pm.fill(Qt.transparent)
            q = QPainter(pm); q.setRenderHint(QPainter.Antialiasing)
            g = QRadialGradient(size / 2, size / 2, size / 2)
            for pos, a in ((0.0, 255), (0.16, 170), (0.45, 48), (1.0, 0)):
                c = QColor(color); c.setAlpha(a); g.setColorAt(pos, c)
            q.setPen(Qt.NoPen); q.setBrush(QBrush(g)); q.drawEllipse(0, 0, size, size); q.end()
            self._spr[key] = pm
        return pm

    def _get(self, key, fab):
        v = self._c2.get(key)
        if v is None:
            if len(self._c2) > 90:
                self._c2.clear()
            v = self._c2[key] = fab()
        return v

    def _radial(self, size, rad, stops, col, op):
        pm = QPixmap(size, size); pm.fill(Qt.transparent)
        q = QPainter(pm); q.setRenderHint(QPainter.Antialiasing); q.setCompositionMode(QPainter.CompositionMode_Plus)
        g = QRadialGradient(size / 2, size / 2, rad)
        for pos, a in stops:
            c = QColor(col); c.setAlpha(int(a * op)); g.setColorAt(pos, c)
        q.setPen(Qt.NoPen); q.setBrush(QBrush(g)); q.drawEllipse(QPointF(size / 2, size / 2), rad, rad); q.end()
        return pm

    def _mk_halo(self, st, R):
        D = int(R * 4.4) | 1
        pm = QPixmap(D, D); pm.fill(Qt.transparent)
        q = QPainter(pm); q.setCompositionMode(QPainter.CompositionMode_Plus)
        for col, rad, op in ((st["a"], R * 2.2, 0.42 * st["glow"]), (st["b"], R * 1.5, 0.20 * st["glow"])):
            q.drawPixmap(0, 0, self._radial(D, rad, ((0.0, 255), (0.2, 170), (0.55, 48), (1.0, 0)), col, op))
        q.end()
        return pm

    def _mk_disco(self, R):
        D = int(R * 1.9) | 1
        pm = QPixmap(D, D); pm.fill(Qt.transparent)
        q = QPainter(pm); q.setRenderHint(QPainter.Antialiasing)
        g = QRadialGradient(D / 2 - R * 0.25, D / 2 - R * 0.30, R * 1.15)
        g.setColorAt(0.0, QColor(20, 36, 70, 235)); g.setColorAt(1.0, QColor(4, 9, 20, 248))
        q.setPen(Qt.NoPen); q.setBrush(QBrush(g)); q.drawEllipse(QPointF(D / 2, D / 2), R * 0.94, R * 0.94); q.end()
        return pm

    def _mk_borde(self, st, R):
        D = int(R * 2.1) | 1
        pm = QPixmap(D, D); pm.fill(Qt.transparent)
        q = QPainter(pm); q.setRenderHint(QPainter.Antialiasing)
        rim = QRadialGradient(D / 2, D / 2, R)
        c0 = QColor(st["a"]); c0.setAlpha(0); c1 = QColor(st["b"]); c1.setAlpha(190)
        rim.setColorAt(0.0, c0); rim.setColorAt(0.80, c0); rim.setColorAt(0.965, c1); rim.setColorAt(1.0, c0)
        q.setPen(Qt.NoPen); q.setBrush(QBrush(rim)); q.drawEllipse(QPointF(D / 2, D / 2), R, R); q.end()
        return pm

    def _mk_puntos(self, st):
        out = []
        for col in (st["a"], st["b"]):
            base = self.sprite(col, 64); fila = []
            for b in range(self.NB):
                prof = (b + 0.5) / self.NB
                d = max(3, int(round(2 * (2.2 + 5.2 * prof)))); op = min(1.0, (0.14 + 0.86 * prof) * 0.95)
                pm = QPixmap(d, d); pm.fill(Qt.transparent)
                q = QPainter(pm); q.setRenderHint(QPainter.SmoothPixmapTransform); q.setOpacity(op)
                q.drawPixmap(QRectF(0, 0, d, d), base, QRectF(base.rect())); q.end(); fila.append(pm)
            out.append(fila)
        return out

    def _mk_plumas(self, st, ci, ancho, ratio, n):
        col = st["a"] if ci == 0 else st["b"]; out = []
        for i in range(n):
            c = QColor(col); c.setAlpha(int(255 * (1 - i / n) ** 1.7))
            out.append(QPen(c, ancho / ratio * 0.9, Qt.SolidLine, Qt.FlatCap))
        return out

    def calidad_auto(self, ms_cuadro):
        self._ms.append(ms_cuadro)
        if len(self._ms) < 30:
            return self.calidad
        prom = sum(self._ms) / len(self._ms); self._ms = []
        i = self.ORDEN.index(self.calidad)
        if prom > 20 and i > 0:
            self.calidad = self.ORDEN[i - 1]
        elif prom < 6 and i < 2:
            self.calidad = self.ORDEN[i + 1]
        return self.calidad

    def paint(self, p, rect, t, estado="reposo", nivel=0.0, hud=None, calidad=None,
              cpu=0.23, ram=0.41, perf=None, escala=None):
        cal = self.CAL[calidad or self.calidad]
        hud = cal["hud"] if hud is None else hud
        st = ESTADOS[estado]
        cx, cy = rect.center().x(), rect.center().y()
        R = min(rect.width(), rect.height()) * (escala if escala else (0.185 if hud else 0.34))
        Ri = int(R)
        pulso = 1 + 0.035 * st["pulse"] * math.sin(t * 2.2) + 0.08 * nivel
        p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform)
        marca = [time.perf_counter()]

        def lap(nombre):
            if perf is not None:
                ahora = time.perf_counter(); perf[nombre] = perf.get(nombre, 0.0) + (ahora - marca[0]) * 1000; marca[0] = ahora

        halo = self._get(("halo", estado, Ri), lambda: self._mk_halo(st, R))
        p.setCompositionMode(QPainter.CompositionMode_Plus); p.setOpacity(min(1.0, 0.88 + 0.5 * (pulso - 1)))
        p.drawPixmap(QPointF(cx - halo.width() / 2, cy - halo.height() / 2), halo)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver); p.setOpacity(1.0)
        lap("halo")

        if hud:
            self._hud(p, cx, cy, R, t, QColor(st["a"]), cpu, ram)
        lap("hud")

        ry, rx = t * st["spin"], 0.42 + 0.10 * math.sin(t * 0.3)
        cyr, syr, cxr, sxr = math.cos(ry), math.sin(ry), math.cos(rx), math.sin(rx)
        pts = self.pts[:cal["n"]]; NB = self.NB
        puntos = self._get(("pts", estado), lambda: self._mk_puntos(st))
        Rr = R * 1.03 * pulso; items = []
        for x, y, z, k in pts:
            z1 = -x * syr + z * cyr
            items.append((y * sxr + z1 * cxr, x * cyr + z * syr, y * cxr - z1 * sxr, k))
        items.sort()
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        i_med = 0
        while i_med < len(items) and items[i_med][0] < 0:
            i_med += 1
        self._puntos(p, items[:i_med], cx, cy, Rr, t, puntos, 0.55)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        lap("particulas")

        disco = self._get(("disco", Ri), lambda: self._mk_disco(R))
        p.drawPixmap(QPointF(cx - disco.width() / 2, cy - disco.height() / 2), disco)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        sa, sb, sw = self.sprite(st["a"]), self.sprite(st["b"]), self.sprite("#ffffff", 128)
        for i in range(cal["blobs"]):
            ang = t * (0.55 + 0.22 * i) + i * 1.9
            ox, oy = math.cos(ang) * R * 0.22, math.sin(ang * 1.25) * R * 0.22
            rad = R * (0.62 + 0.08 * math.sin(t * 1.6 + i)) * pulso
            p.setOpacity(0.50 * st["glow"])
            p.drawPixmap(QRectF(cx + ox - rad, cy + oy - rad, 2 * rad, 2 * rad), sa if i % 2 == 0 else sb, QRectF(sa.rect()))
        rc = R * 0.34 * (1 + 0.10 * nivel); p.setOpacity(0.95)
        p.drawPixmap(QRectF(cx - rc, cy - rc, 2 * rc, 2 * rc), sw, QRectF(sw.rect()))
        p.setOpacity(1.0)
        borde = self._get(("borde", estado, Ri), lambda: self._mk_borde(st, R))
        p.drawPixmap(QPointF(cx - borde.width() / 2, cy - borde.height() / 2), borde)
        lap("esfera")

        self._puntos(p, items[i_med:], cx, cy, Rr, t, puntos, 1.0)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        lap("particulas")

        p.setCompositionMode(QPainter.CompositionMode_Plus)
        NSEG = 14
        for j, (rr, ancho, vel, inc, ratio, ci) in enumerate(self.ANILLOS[:cal["anillos"]]):
            plumas = self._get(("plumas", estado, j), lambda ci=ci, ancho=ancho, ratio=ratio: self._mk_plumas(st, ci, ancho, ratio, NSEG))
            ang = (t * 55.0 * vel * (0.6 + st["spin"] * 2)) % 360
            giro = inc + t * 3.0 * st["spin"] * (1 if j % 2 == 0 else -1)
            rad = R * rr
            p.save(); p.translate(cx, cy); p.rotate(giro); p.scale(pulso, pulso * ratio)
            recta = QRectF(-rad, -rad, 2 * rad, 2 * rad); seg = 137.0 / NSEG
            for i in range(NSEG):
                p.setPen(plumas[i]); p.drawArc(recta, int((ang + i * seg) * 16), int((seg + 1.5) * 16))
            p.restore()
            ar = math.radians(ang); rp = rad * pulso
            hx, hy = rp * math.cos(ar), -rp * math.sin(ar) * ratio
            gr = math.radians(giro); gx = hx * math.cos(gr) - hy * math.sin(gr); gy = hx * math.sin(gr) + hy * math.cos(gr)
            p.setOpacity(0.95); p.drawPixmap(QRectF(cx + gx - 9, cy + gy - 9, 18, 18), sw, QRectF(sw.rect())); p.setOpacity(1.0)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        lap("anillos")

        if nivel > 0.01 and cal["onda"]:
            p.setCompositionMode(QPainter.CompositionMode_Plus)
            base = R * 1.12 * pulso; la, lb = [], []
            for k in range(96):
                a = k / 96 * 2 * math.pi
                v = 0.5 + 0.5 * math.sin(a * 7 + t * 9) * math.sin(a * 3 - t * 5)
                L = R * (0.04 + 0.20 * nivel * v); ca_, sa_ = math.cos(a), math.sin(a)
                (lb if k % 2 else la).append(QLineF(cx + ca_ * base, cy + sa_ * base, cx + ca_ * (base + L), cy + sa_ * (base + L)))
            for lineas, col in ((la, st["a"]), (lb, st["b"])):
                c = QColor(col); c.setAlpha(185); p.setPen(QPen(c, 2.2, Qt.SolidLine, Qt.RoundCap)); p.drawLines(lineas)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setOpacity(1.0)
        lap("onda")

    def _puntos(self, p, lista, cx, cy, Rr, t, puntos, fuerza):
        NB = self.NB
        for z2, x1, y1, k in lista:
            prof = (z2 + 1) / 2
            tw = 0.72 + 0.28 * math.sin(t * 2.0 + k * 50)
            b = int(prof * tw * NB)
            if b >= NB: b = NB - 1
            pm = puntos[1 if prof > 0.62 else 0][b]
            p.drawPixmap(int(cx + x1 * Rr - pm.width() / 2), int(cy + y1 * Rr - pm.height() / 2), pm)

    def _hud(self, p, cx, cy, R, t, ca, cpu, ram):
        rd = R * 1.95; largas, cortas = [], []
        for i in range(72):
            a = math.radians(i * 5 - t * 4); co, si = math.cos(a), math.sin(a)
            n = 11 if i % 6 == 0 else 5
            (largas if i % 6 == 0 else cortas).append(QLineF(cx + co * rd, cy + si * rd, cx + co * (rd + n), cy + si * (rd + n)))
        c = QColor(ca); c.setAlpha(105); p.setPen(QPen(c, 1.4)); p.drawLines(largas)
        c = QColor(ca); c.setAlpha(38); p.setPen(QPen(c, 1.0)); p.drawLines(cortas)
        rm = QRectF(cx - R * 2.22, cy - R * 2.22, R * 4.44, R * 4.44)
        for centro, val, nombre in ((180, cpu, "CPU"), (0, ram, "RAM")):
            base = QColor(ca); base.setAlpha(36)
            p.setPen(QPen(base, 5, Qt.SolidLine, Qt.RoundCap)); p.drawArc(rm, int((centro - 36) * 16), int(72 * 16))
            fill = QColor(ca); fill.setAlpha(215)
            p.setPen(QPen(fill, 5, Qt.SolidLine, Qt.RoundCap)); p.drawArc(rm, int((centro - 36) * 16), int(72 * val * 16))
            tx = cx + (-1 if centro == 180 else 1) * (R * 2.22 + 18)
            texto(p, tx, cy - 4, nombre, 11, "#94a3b8", esp=2, alinear="r" if centro == 180 else "l")
            texto(p, tx, cy + 16, "%d%%" % int(val * 100), 15, "#e2e8f0", bold=True, alinear="r" if centro == 180 else "l")

def fondo(p, w, h):
    g = QRadialGradient(w / 2, h / 2, max(w, h) * 0.75)
    g.setColorAt(0.0, QColor("#13213f")); g.setColorAt(0.55, QColor(BG0)); g.setColorAt(1.0, QColor(BG1))
    p.fillRect(0, 0, w, h, QBrush(g))

def renderizar(salida="."):
    elegir_fuente()
    nucleo = Nucleo()
    ancho = 340
    img = QImage(ancho * 5, 380, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(img); fondo(p, img.width(), img.height())
    for i, e in enumerate(ESTADOS):
        nucleo.paint(p, QRectF(i * ancho, 0, ancho, 340), 4.0 + i * 0.7, e,
                     nivel={"hablando": 0.8, "escuchando": 0.5, "alerta": 0.3}.get(e, 0.0), calidad="alta", hud=False, escala=0.30)
    p.end(); img.save(salida + "/aria_nucleo_estados.png")
    W, H = 1360, 800
    img = QImage(W, H, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    fondo(p, W, H)
    nucleo.paint(p, QRectF(W / 2 - 260, H / 2 - 260, 520, 520), 5.3, "hablando", 0.75, calidad="alta", hud=True)
    p.end(); img.save(salida + "/aria_ui_mockup.png")

def medir(nucleo, tam=900, cuadros=160, calentamiento=10):
    img = QImage(tam, tam, QImage.Format_ARGB32_Premultiplied)
    print("tam=%dx%d  cuadros=%d (se descartan %d de calentamiento)" % (tam, tam, cuadros, calentamiento))
    for cal in ("alta", "media", "baja"):
        nucleo._c2.clear(); ms, perf = [], {}
        for k in range(cuadros):
            p = QPainter(img); img.fill(QColor(BG0)); t0 = time.perf_counter()
            nucleo.paint(p, QRectF(0, 0, tam, tam), k / 30.0, "hablando", 0.7, calidad=cal, escala=0.185, perf=perf if k >= calentamiento else None)
            dt = (time.perf_counter() - t0) * 1000; p.end()
            if k >= calentamiento: ms.append(dt)
        ms.sort(); n = len(ms)
        sec = {k: round(v / n, 2) for k, v in perf.items()}
        print("  %-5s media=%5.1f ms  p95=%5.1f ms  max=%5.1f   secciones(ms)=%s" % (cal, sum(ms) / n, ms[int(n * .95)], ms[-1], sec))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    destino = sys.argv[1] if len(sys.argv) > 1 else "."
    if "--medir" in sys.argv:
        elegir_fuente(); medir(Nucleo())
    else:
        renderizar(destino)
