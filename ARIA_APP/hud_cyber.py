# -*- coding: utf-8 -*-
"""ARIA - HUD cyberpunk estilo Linux (PyQt5, QPainter). Overlay de escritorio.

Marco angular, monitores de sistema (CPU/RAM/disco), feed de terminal, reloj,
scanlines y glitch sutil. Paleta cian (#38bdf8) sobre oscuro. Sin servidores.
Frameless, translucido, top-most, arrastrable. psutil opcional (si no, simula).
"""
import os
import time
import math
import random
from collections import deque

from PyQt5.QtCore import Qt, QRectF, QPointF, QTimer, QPoint
from PyQt5.QtGui import (QPainter, QColor, QPen, QBrush, QFont, QLinearGradient,
                         QPainterPath, QFontDatabase)
from PyQt5.QtWidgets import QWidget, QApplication

CYAN = QColor("#38bdf8")
CYAN_DIM = QColor(56, 189, 248, 70)
VERDE = QColor("#7dffb0")
BG0 = QColor(8, 14, 28, 225)
BG1 = QColor(4, 8, 18, 235)
TXT = QColor("#cfe8ff")
ROJO = QColor("#fb7185")

_MONO = "Consolas"


def _elegir_mono():
    global _MONO
    fams = set(QFontDatabase().families())
    for f in ("Cascadia Mono", "Consolas", "JetBrains Mono", "DejaVu Sans Mono", "Courier New"):
        if f in fams:
            _MONO = f
            return


def _stats():
    try:
        import psutil
        return (psutil.cpu_percent(interval=None) / 100.0,
                psutil.virtual_memory().percent / 100.0,
                psutil.disk_usage("/").percent / 100.0)
    except Exception:
        t = time.time()
        return (0.35 + 0.25 * math.sin(t * 0.7), 0.52 + 0.1 * math.sin(t * 0.3), 0.61)


def _fuente(p, px, bold=False, mono=True):
    f = QFont(_MONO if mono else "Segoe UI", px)
    f.setBold(bold)
    f.setStyleHint(QFont.Monospace)
    p.setFont(f)
    return f


class HudCyber(QWidget):
    def __init__(self, w=560, h=360):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(w, h)
        self._w, self._h = w, h
        self._t0 = time.time()
        self._cpu = self._ram = self._disk = 0.0
        self._cpu_hist = deque([0.0] * 60, maxlen=60)
        self._estado = "EN LINEA"
        self._feed = deque(maxlen=7)
        self._glitch = 0.0
        self._drag = None
        for linea in ("ARIA core cargado", "cerebro local: llama.cpp", "modo: RAIDEN",
                      "skills activas", "esperando ordenes_"):
            self._feed.append(linea)

    def log(self, texto):
        self._feed.append(str(texto)[:60])
        self._glitch = 1.0
        self.update()

    def set_estado(self, e):
        self._estado = str(e).upper()
        self._glitch = 1.0

    def start(self):
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(120)
        scr = QApplication.primaryScreen().availableGeometry() if QApplication.instance() else None
        if scr:
            self.move(scr.right() - self._w - 24, scr.top() + 24)
        self.show()

    def _tick(self):
        self._cpu, self._ram, self._disk = _stats()
        self._cpu_hist.append(self._cpu)
        if self._glitch > 0:
            self._glitch = max(0.0, self._glitch - 0.12)
        self.update()

    # ---- arrastre ----
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPos() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPos() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    # ---- pintura ----
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        t = time.time() - self._t0
        W, H = self._w, self._h
        self._fondo(p, W, H)
        self._marco(p, W, H, t)
        self._cabecera(p, W, t)
        self._barras(p, 22, 78, 250)
        self._grafica_cpu(p, 300, 82, W - 322, 86)
        self._terminal(p, 22, 196, W - 44, H - 214, t)
        self._scanlines(p, W, H)
        if self._glitch > 0.01:
            self._glitch_fx(p, W, H)
        p.end()

    def _fondo(self, p, W, H):
        g = QLinearGradient(0, 0, 0, H)
        g.setColorAt(0, BG0); g.setColorAt(1, BG1)
        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, W - 2, H - 2), 10, 10)
        p.fillPath(path, QBrush(g))

    def _marco(self, p, W, H, t):
        p.setPen(QPen(CYAN_DIM, 1.2))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 10, 10)
        # esquinas angulares brillantes
        p.setPen(QPen(CYAN, 2.2))
        L = 26
        for (x, y, dx, dy) in ((8, 8, 1, 1), (W - 8, 8, -1, 1), (8, H - 8, 1, -1), (W - 8, H - 8, -1, -1)):
            p.drawLine(QPointF(x, y), QPointF(x + dx * L, y))
            p.drawLine(QPointF(x, y), QPointF(x, y + dy * L))
        # linea superior animada (barrido)
        xs = 20 + (W - 40) * (0.5 + 0.5 * math.sin(t * 0.8))
        grad = QColor(CYAN); grad.setAlpha(160)
        p.setPen(QPen(grad, 1))
        p.drawLine(QPointF(20, 60), QPointF(W - 20, 60))
        p.setBrush(CYAN); p.setPen(Qt.NoPen)
        p.drawRect(QRectF(xs - 14, 59, 28, 2))

    def _cabecera(self, p, W, t):
        _fuente(p, 20, bold=True)
        p.setPen(CYAN)
        p.drawText(QRectF(22, 14, 300, 30), Qt.AlignVCenter, "ARIA")
        _fuente(p, 10)
        p.setPen(TXT)
        p.drawText(QRectF(92, 16, 300, 16), Qt.AlignVCenter, "// SYSTEM MONITOR")
        # estado con punto parpadeante
        on = (int(t * 2) % 2 == 0)
        col = VERDE if "LINEA" in self._estado or "RAIDEN" in self._estado else ROJO
        p.setBrush(col if on else QColor(col.red(), col.green(), col.blue(), 60)); p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(96, 36), 4, 4)
        _fuente(p, 10, bold=True); p.setPen(col)
        p.drawText(QRectF(108, 28, 220, 16), Qt.AlignVCenter, self._estado)
        # reloj
        _fuente(p, 12, bold=True); p.setPen(CYAN)
        reloj = time.strftime("%H:%M:%S")
        p.drawText(QRectF(W - 150, 16, 128, 18), Qt.AlignRight | Qt.AlignVCenter, reloj)
        _fuente(p, 9); p.setPen(TXT)
        p.drawText(QRectF(W - 180, 34, 158, 14), Qt.AlignRight, time.strftime("%Y-%m-%d"))

    def _barra(self, p, x, y, w, label, val, col):
        _fuente(p, 9, bold=True); p.setPen(TXT)
        p.drawText(QRectF(x, y - 14, 60, 12), Qt.AlignLeft, label)
        _fuente(p, 9); p.setPen(col)
        p.drawText(QRectF(x + w - 40, y - 14, 40, 12), Qt.AlignRight, "%d%%" % int(val * 100))
        # pista segmentada
        seg, gap = 7, 3
        n = int(w / (seg + gap))
        llenos = int(n * val)
        for i in range(n):
            bx = x + i * (seg + gap)
            c = QColor(col) if i < llenos else QColor(col.red(), col.green(), col.blue(), 45)
            p.setBrush(c); p.setPen(Qt.NoPen)
            p.drawRect(QRectF(bx, y, seg, 9))

    def _barras(self, p, x, y, w):
        datos = (("CPU", self._cpu, CYAN), ("RAM", self._ram, QColor("#a78bfa")),
                 ("DISCO", self._disk, QColor("#2dd4bf")))
        for i, (lab, val, col) in enumerate(datos):
            self._barra(p, x, y + i * 40, w, lab, val, col)

    def _grafica_cpu(self, p, x, y, w, h):
        p.setPen(QPen(CYAN_DIM, 1))
        p.drawRect(QRectF(x, y, w, h))
        _fuente(p, 8); p.setPen(CYAN_DIM)
        p.drawText(QRectF(x + 4, y + 2, 120, 12), Qt.AlignLeft, "CPU // 60s")
        hist = list(self._cpu_hist)
        n = len(hist)
        path = QPainterPath()
        for i, v in enumerate(hist):
            px = x + w * i / (n - 1)
            py = y + h - (h - 4) * v - 2
            path.moveTo(px, py) if i == 0 else path.lineTo(px, py)
        p.setPen(QPen(CYAN, 1.6)); p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        # relleno tenue
        path.lineTo(x + w, y + h); path.lineTo(x, y + h); path.closeSubpath()
        p.setPen(Qt.NoPen); p.setBrush(CYAN_DIM); p.drawPath(path)

    def _terminal(self, p, x, y, w, h, t):
        p.setPen(QPen(CYAN_DIM, 1)); p.setBrush(QColor(2, 6, 14, 160))
        p.drawRoundedRect(QRectF(x, y, w, h), 6, 6)
        _fuente(p, 8, bold=True); p.setPen(CYAN_DIM)
        p.drawText(QRectF(x + 8, y + 4, 200, 12), Qt.AlignLeft, "root@aria:~#")
        _fuente(p, 10);
        lineas = list(self._feed)
        ly = y + 24
        for i, ln in enumerate(lineas):
            p.setPen(VERDE if i == len(lineas) - 1 else TXT)
            cursor = "_" if (i == len(lineas) - 1 and int(t * 2) % 2 == 0) else ""
            p.drawText(QRectF(x + 10, ly, w - 20, 16), Qt.AlignLeft, "> " + ln + cursor)
            ly += 18

    def _scanlines(self, p, W, H):
        p.setPen(QPen(QColor(56, 189, 248, 14), 1))
        for y in range(2, H, 3):
            p.drawLine(2, y, W - 2, y)

    def _glitch_fx(self, p, W, H):
        a = int(90 * self._glitch)
        for _ in range(int(6 * self._glitch)):
            gy = random.randint(0, H - 6)
            gh = random.randint(2, 6)
            dx = random.randint(-8, 8)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 60, 90, a // 2))
            p.drawRect(QRectF(2 + dx, gy, W - 4, gh))
            p.setBrush(QColor(56, 189, 248, a // 2))
            p.drawRect(QRectF(2 - dx, gy + 1, W - 4, gh))


def crear_hud(w=560, h=360):
    _elegir_mono()
    return HudCyber(w, h)
