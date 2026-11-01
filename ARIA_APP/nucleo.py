# -*- coding: utf-8 -*-
"""ARIA - Nucleo visual VIVO (robado de Brahma Evo + cuerpo reactivo).

El nucleo NO es un adorno estatico: es el CUERPO de ARIA. Siente el mouse y reacciona
como si estuviera viva:
  - MIRA hacia el cursor (el orbe se inclina/desplaza hacia donde esta el mouse).
  - SE EXCITA al acercarse el cursor (mas brillo, gira mas rapido, late mas fuerte).
  - PULSA al tocarlo (click = estallido de energia).
  - RESPIRA cuando esta sola (escala sutil, movimiento organico).
  - las particulas se atraen hacia el cursor y se aceleran con la cercania.

Orbe = espirografo (hipotrocoide) de lineas finas cyan sobre campo de estrellas, con
anillos orbitales y glow. Paleta cyan de ARIA (#38bdf8). Frameless/translucido/topmost.

La matematica del orbe (_espirografo) y de la reaccion al mouse (_reaccion) son PURAS
(sin Qt): testeables sin pantalla. El render usa QPainter (sin deps nuevas).
"""
import math
import random

try:
    from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF
    from PyQt5.QtGui import QPainter, QColor, QPen, QRadialGradient, QCursor
    from PyQt5.QtWidgets import QWidget, QApplication
    _QT = True
except Exception:
    _QT = False

CYAN = (56, 189, 248)       # #38bdf8 (paleta ARIA)
TEAL = (45, 212, 191)
BLANCO = (220, 240, 255)


def _espirografo(R, r, d, vueltas=24, n=720):
    """Hipotrocoide (espirografo). Puntos (x,y) normalizados ~[-1,1]. Puro, testeable."""
    pts = []
    if r == 0:
        r = 1
    k = (R - r) / float(r)
    maxrad = abs(R - r) + abs(d) or 1.0
    paso = (2 * math.pi * vueltas) / n
    for i in range(n + 1):
        t = i * paso
        x = (R - r) * math.cos(t) + d * math.cos(k * t)
        y = (R - r) * math.sin(t) - d * math.sin(k * t)
        pts.append((x / maxrad, y / maxrad))
    return pts


def _reaccion(cx, cy, mx, my, alcance=440, max_lean=22):
    """Dada la posicion del orbe (cx,cy) y del mouse (mx,my), devuelve:
      prox  = cercania 0..1 (1 = encima, 0 = lejos/fuera de alcance)
      lx,ly = cuanto 'mira'/se inclina el orbe hacia el cursor (px)
    Puro, sin Qt -> testeable."""
    dx, dy = mx - cx, my - cy
    dist = math.hypot(dx, dy)
    prox = max(0.0, 1.0 - dist / float(alcance))
    if dist > 1e-6:
        lx = (dx / dist) * max_lean * prox
        ly = (dy / dist) * max_lean * prox
    else:
        lx = ly = 0.0
    return prox, lx, ly


def _lerp(a, b, k):
    return a + (b - a) * k


def _decidir_modo(prox, modo, idle, umbral_frente=0.35, umbral_fondo=0.1, frames_fondo=90):
    """Presencia -> modo de ventana. Si el mouse se acerca (prox alto) ARIA pasa al
    FRENTE; si llevas un rato lejos, vuelve al FONDO (detras de las otras ventanas).
    Con histeresis para no parpadear. Puro, testeable. Devuelve (modo, idle)."""
    if prox >= umbral_frente:
        return "frente", 0
    if prox <= umbral_fondo:
        idle += 1
        if idle >= frames_fondo and modo != "fondo":
            return "fondo", idle
    return modo, idle


if _QT:
    class Nucleo(QWidget):
        def __init__(self, size=340, modo="fondo"):
            super().__init__(None)
            self._modo = modo                 # 'fondo' (detras de todo) | 'frente' | 'normal'
            self._idle = 0
            self.setWindowFlags(self._flags(modo))
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)   # no roba el foco
            self.setMouseTracking(True)
            self.resize(size, size)
            self._s = size
            self._t = 0.0
            self._estado = "idle"
            self._drag = None
            # vida reactiva (valores suavizados)
            self._prox = 0.0          # cercania del mouse
            self._lean = [0.0, 0.0]   # cuanto mira hacia el cursor
            self._pulse = 0.0         # estallido al tocar
            self._resp = 0.0          # fase de respiracion
            self._estrellas = [(random.random(), random.random(),
                                random.uniform(0.3, 1.0), random.uniform(0.5, 2.0))
                               for _ in range(90)]
            self._curva_a = _espirografo(220, 68, 110, vueltas=22, n=680)
            self._curva_b = _espirografo(200, 50, 130, vueltas=16, n=520)
            self._part = [(random.uniform(0, 2 * math.pi), random.uniform(0.6, 1.05),
                           random.uniform(0.4, 1.3)) for _ in range(24)]

        def set_estado(self, e):
            self._estado = str(e)

        def _flags(self, modo):
            base = Qt.FramelessWindowHint | Qt.Tool
            if modo == "frente":
                return base | Qt.WindowStaysOnTopHint
            if modo == "fondo":
                return base | Qt.WindowStaysOnBottomHint   # pegada al escritorio, detras de todo
            return base

        def set_modo(self, modo):
            """Cambia el modo de ventana. 'fondo' = detras de las demas apps (segundo
            plano); 'frente' = encima; 'normal' = ventana comun. No roba el foco."""
            if modo == self._modo:
                return
            self._modo = modo
            self.setWindowFlags(self._flags(modo))
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
            self.show()        # re-mostrar tras cambiar flags (sin activar/robar foco)

        def start(self, fps=30):
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(int(1000 / fps))
            scr = QApplication.primaryScreen().availableGeometry() if QApplication.instance() else None
            if scr:
                self.move(scr.center().x() - self._s // 2, scr.center().y() - self._s // 2)
            self.show()

        def _tick(self):
            self._t += 0.016
            self._resp += 0.016
            # sentir el mouse (global), aunque el cursor este fuera de la ventana
            try:
                g = QCursor.pos()
                cen = self.mapToGlobal(self.rect().center())
                prox_obj, lx, ly = _reaccion(cen.x(), cen.y(), g.x(), g.y())
            except Exception:
                prox_obj, lx, ly = 0.0, 0.0, 0.0
            # suavizar (la vida no da saltos)
            self._prox = _lerp(self._prox, prox_obj, 0.12)
            self._lean[0] = _lerp(self._lean[0], lx, 0.15)
            self._lean[1] = _lerp(self._lean[1], ly, 0.15)
            if self._pulse > 0:
                self._pulse = max(0.0, self._pulse - 0.04)
            # presencia -> segundo plano cuando no estas; al frente cuando te acercas
            nuevo, self._idle = _decidir_modo(prox_obj, self._modo, self._idle)
            if nuevo != self._modo:
                self.set_modo(nuevo)
            self.update()

        # ---- arrastre + pulso al tocar ----
        def mousePressEvent(self, e):
            if e.button() == Qt.LeftButton:
                self._drag = e.globalPos() - self.pos()
                self._pulse = 1.0          # tocarla = estallido de energia

        def mouseMoveEvent(self, e):
            if self._drag is not None:
                self.move(e.globalPos() - self._drag)

        def mouseReleaseEvent(self, e):
            self._drag = None

        def enterEvent(self, e):
            self._pulse = max(self._pulse, 0.5)   # reacciona al entrar el cursor

        # ---- animo: estado base + cercania del mouse ----
        def _animo(self):
            base = {"pensando": (1.9, 1.0), "hablando": (1.3, 0.9)}.get(self._estado, (0.7, 0.72))
            vel, brillo = base
            vel += self._prox * 1.4                 # mas cerca -> gira mas rapido
            brillo = min(1.0, brillo + self._prox * 0.45 + self._pulse * 0.5)
            return vel, brillo

        # ---- pintura ----
        def paintEvent(self, e):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            S = self._s
            vel, brillo = self._animo()
            # respiracion + inclinacion hacia el cursor = cuerpo vivo
            resp = 1.0 + 0.025 * math.sin(self._resp * 1.4) + 0.05 * self._pulse
            cx = S / 2 + self._lean[0]
            cy = S / 2 + self._lean[1]
            t = self._t

            self._fondo(p, S)
            self._estrellas_draw(p, S, t)
            self._glow(p, cx, cy, S, brillo, t, resp)
            self._anillos(p, cx, cy, S, t * vel)
            self._orbe(p, cx, cy, S, t * vel, brillo, resp)
            self._particulas(p, cx, cy, S, t * vel, brillo)
            p.end()

        def _fondo(self, p, S):
            g = QRadialGradient(S / 2, S / 2, S / 2)
            g.setColorAt(0, QColor(10, 18, 34, 235))
            g.setColorAt(1, QColor(4, 8, 18, 245))
            p.setBrush(g); p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(0, 0, S, S))

        def _estrellas_draw(self, p, S, t):
            p.setPen(Qt.NoPen)
            for sx, sy, br, vel in self._estrellas:
                a = int(120 * br * (0.5 + 0.5 * math.sin(t * vel + sx * 10)))
                p.setBrush(QColor(BLANCO[0], BLANCO[1], BLANCO[2], max(0, a)))
                p.drawEllipse(QPointF(sx * S, sy * S), br, br)

        def _glow(self, p, cx, cy, S, brillo, t, resp):
            rad = S * 0.34 * resp * (1 + 0.04 * math.sin(t * 2))
            g = QRadialGradient(cx, cy, rad)
            g.setColorAt(0, QColor(CYAN[0], CYAN[1], CYAN[2], int(70 * brillo)))
            g.setColorAt(0.6, QColor(TEAL[0], TEAL[1], TEAL[2], int(22 * brillo)))
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(g); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(cx, cy), rad, rad)

        def _anillos(self, p, cx, cy, S, t):
            rad = S * 0.42
            for i in range(3):
                ang = t * (0.2 + 0.12 * i) + i * 1.1
                p.save()
                p.translate(cx, cy)
                p.rotate(math.degrees(ang))
                p.setPen(QPen(QColor(CYAN[0], CYAN[1], CYAN[2], 60), 1.0))
                p.setBrush(Qt.NoBrush)
                rx = rad * (0.9 - 0.12 * i)
                ry = rx * (0.32 + 0.1 * i)
                p.drawEllipse(QRectF(-rx, -ry, 2 * rx, 2 * ry))
                p.restore()

        def _orbe(self, p, cx, cy, S, t, brillo, resp):
            escala = S * 0.3 * resp
            p.save()
            p.translate(cx, cy)
            p.rotate(math.degrees(t * 0.25))
            for curva, col, alpha in ((self._curva_a, CYAN, int(70 * brillo)),
                                      (self._curva_b, TEAL, int(55 * brillo))):
                p.setPen(QPen(QColor(col[0], col[1], col[2], alpha), 1.0))
                prev = None
                for (x, y) in curva:
                    pt = QPointF(x * escala, y * escala)
                    if prev is not None:
                        p.drawLine(prev, pt)
                    prev = pt
            p.restore()

        def _particulas(self, p, cx, cy, S, t, brillo):
            p.setPen(Qt.NoPen)
            # las particulas se dejan arrastrar hacia donde 'mira' el orbe (el cursor)
            pull_x = self._lean[0] * 1.5
            pull_y = self._lean[1] * 1.5
            for base, radio, vel in self._part:
                ang = base + t * vel * (0.5 + self._prox)   # mas cerca -> mas rapidas
                r = S * 0.30 * radio
                x = cx + r * math.cos(ang) + pull_x
                y = cy + r * math.sin(ang) * 0.5 + pull_y
                a = int(180 * brillo * (0.4 + 0.6 * abs(math.sin(ang))))
                p.setBrush(QColor(BLANCO[0], BLANCO[1], BLANCO[2], a))
                p.drawEllipse(QPointF(x, y), 1.4 + 1.2 * self._pulse, 1.4 + 1.2 * self._pulse)


    def crear_nucleo(size=340):
        return Nucleo(size)
else:
    def crear_nucleo(size=340):
        return {"error": "PyQt5 no disponible"}
