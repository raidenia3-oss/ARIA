# -*- coding: utf-8 -*-
"""ARIA Chibi - avatar de escritorio para ARIA (PyQt5, un proceso, sin red/servidores).

Hibrido: capa base por SPRITE SHEET (arte) + capa de EXPRESIONES procedural (QPainter).
Si no hay sheet, genera un placeholder dibujado por codigo (paleta plata/cian: fusion
Ciel+Iroha+Echidna). Bajo consumo: timers ~12 fps, motor raster (sin GPU).

Integracion: conecta los slots on_pensando/on_escuchando/on_respondio/on_idle a las
senales de estado de ARIA; escucha pedir_abrir para enfocar la ventana principal.
"""
import os
import json
import math
import time
import random
from enum import Enum
from dataclasses import dataclass

from PyQt5.QtCore import Qt, QRect, QRectF, QPoint, QPointF, QTimer, QObject, pyqtSignal
from PyQt5.QtGui import (QPixmap, QPainter, QColor, QPen, QBrush, QRadialGradient,
                         QFont, QCursor, QPainterPath)
from PyQt5.QtWidgets import QWidget, QApplication

CYAN = "#38bdf8"
PLATA = "#e8edf4"
_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(_DIR, "data")
_ASSETS = os.path.join(_DIR, "assets", "chibi")


class ChibiState(Enum):
    IDLE = "idle"; WALK = "walk"; TALK = "talk"; THINK = "think"
    LISTEN = "listen"; SLEEP = "sleep"; REACT = "react"


@dataclass
class EstadoAnim:
    fila: int
    frames: int
    fps: int
    loop: bool = True


DEFAULT_STATES = {
    ChibiState.IDLE:   EstadoAnim(0, 4, 8),
    ChibiState.WALK:   EstadoAnim(1, 6, 12),
    ChibiState.TALK:   EstadoAnim(2, 4, 12),
    ChibiState.THINK:  EstadoAnim(3, 4, 8),
    ChibiState.LISTEN: EstadoAnim(4, 4, 10),
    ChibiState.SLEEP:  EstadoAnim(5, 2, 4),
    ChibiState.REACT:  EstadoAnim(6, 4, 14, loop=False),
}
_MAX_FRAMES = max(a.frames for a in DEFAULT_STATES.values())


# ============================================================ SPRITE SHEET
class SpriteSheet:
    def __init__(self, tema_dir, frame_w=160, frame_h=160, states=None):
        self.fw, self.fh = frame_w, frame_h
        self.states = states or DEFAULT_STATES
        # si el tema trae config.json (sheet generado), usarlo
        cfgp = os.path.join(tema_dir, "config.json") if tema_dir else ""
        if cfgp and os.path.isfile(cfgp):
            try:
                c = json.load(open(cfgp, encoding="utf-8"))
                self.fw = int(c.get("frame_w", self.fw))
                self.fh = int(c.get("frame_h", self.fh))
                st = {}
                for k, v in (c.get("states") or {}).items():
                    try:
                        st[ChibiState(k)] = EstadoAnim(int(v["fila"]), int(v.get("frames", 1)),
                                                       int(v.get("fps", 8)), bool(v.get("loop", True)))
                    except Exception:
                        pass
                if st:
                    self.states = st
            except Exception:
                pass
        ruta = os.path.join(tema_dir, "sheet.png") if tema_dir else ""
        pm = QPixmap(ruta) if ruta and os.path.isfile(ruta) else QPixmap()
        if pm.isNull():
            pm = self._placeholder()
            self.placeholder = True
        else:
            self.placeholder = False
        self.pixmap = pm

    def frame(self, estado, i):
        a = self.states[estado]
        i = i % a.frames
        return QRect(i * self.fw, a.fila * self.fh, self.fw, self.fh)

    def _placeholder(self):
        cols, filas = _MAX_FRAMES, len(self.states)
        pm = QPixmap(cols * self.fw, filas * self.fh)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        for est, a in self.states.items():
            for i in range(a.frames):
                r = QRect(i * self.fw, a.fila * self.fh, self.fw, self.fh)
                _dibujar_chibi_base(p, r, est, i)
        p.end()
        return pm


def _dibujar_chibi_base(p, r, estado, frame):
    """Chibi placeholder ORIGINAL por codigo (reemplazable por el arte real del sheet).

    Diseno propio inspirado en los rasgos (pelo plata largo, ojos cian grandes,
    audifonos, visor cyber). No reproduce ningun personaje con copyright.
    """
    W = r.width()
    cx = r.x() + W / 2.0
    bob = math.sin(frame * 1.3) * (r.height() * 0.012)
    durmiendo = estado == ChibiState.SLEEP
    ch_r = W * 0.30
    ch_y = r.y() + r.height() * 0.40 + bob
    base_y = ch_y + ch_r * 1.15

    p.setPen(Qt.NoPen)
    # --- coletas/mechones largos plata detras (Echidna) ---
    p.setBrush(QColor("#dfe6f0"))
    for dx in (-1, 1):
        cola = QPainterPath()
        cola.moveTo(cx + dx * ch_r * 0.8, ch_y - ch_r * 0.2)
        cola.cubicTo(cx + dx * ch_r * 1.5, ch_y + ch_r * 0.6,
                     cx + dx * ch_r * 1.3, base_y + ch_r * 0.5,
                     cx + dx * ch_r * 0.7, base_y + ch_r * 0.2)
        cola.cubicTo(cx + dx * ch_r * 1.0, base_y, cx + dx * ch_r * 0.9, ch_y + ch_r * 0.3,
                     cx + dx * ch_r * 0.8, ch_y - ch_r * 0.2)
        p.fillPath(cola, QBrush(QColor("#dfe6f0")))
    # --- cuerpo (traje cian con degradado) ---
    cuerpo = QPainterPath()
    cuerpo.addRoundedRect(QRectF(cx - W * 0.17, base_y, W * 0.34, r.height() * 0.24), 16, 16)
    g = QRadialGradient(cx, base_y + r.height() * 0.1, W * 0.32)
    g.setColorAt(0, QColor(70, 140, 190)); g.setColorAt(1, QColor(18, 36, 64))
    p.fillPath(cuerpo, QBrush(g))
    # cuellito / bufanda cian
    p.setBrush(QColor(CYAN))
    p.drawRoundedRect(QRectF(cx - W * 0.12, base_y - ch_r * 0.08, W * 0.24, ch_r * 0.22), 8, 8)
    # --- pelo plata (volumen detras) ---
    p.setBrush(QColor(PLATA))
    p.drawEllipse(QPointF(cx, ch_y + ch_r * 0.1), ch_r * 1.16, ch_r * 1.24)
    # --- cara ---
    p.setBrush(QColor("#fff0e2"))
    p.drawEllipse(QPointF(cx, ch_y), ch_r, ch_r * 1.02)
    # rubor suave por defecto
    p.setBrush(QColor(255, 150, 165, 90))
    for dx in (-ch_r * 0.52, ch_r * 0.52):
        p.drawEllipse(QPointF(cx + dx, ch_y + ch_r * 0.32), ch_r * 0.16, ch_r * 0.1)
    # --- flequillo plata al frente ---
    p.setBrush(QColor(PLATA))
    fle = QPainterPath()
    fle.moveTo(cx - ch_r, ch_y - ch_r * 0.1)
    fle.cubicTo(cx - ch_r * 0.9, ch_y - ch_r * 1.1, cx + ch_r * 0.9, ch_y - ch_r * 1.1,
                cx + ch_r, ch_y - ch_r * 0.1)
    fle.cubicTo(cx + ch_r * 0.5, ch_y - ch_r * 0.5, cx + ch_r * 0.2, ch_y - ch_r * 0.35,
                cx, ch_y - ch_r * 0.5)
    fle.cubicTo(cx - ch_r * 0.2, ch_y - ch_r * 0.35, cx - ch_r * 0.5, ch_y - ch_r * 0.5,
                cx - ch_r, ch_y - ch_r * 0.1)
    p.fillPath(fle, QBrush(QColor(PLATA)))
    # visor cyber cian (de Ciel) : banda translucida en la frente
    p.setBrush(QColor(56, 189, 248, 70))
    p.drawRoundedRect(QRectF(cx - ch_r * 0.75, ch_y - ch_r * 0.25, ch_r * 1.5, ch_r * 0.16), 6, 6)
    # --- ojos cian grandes con brillo ---
    ojo_y = ch_y + ch_r * 0.12
    parpadea = (frame % 5 == 4) or durmiendo
    for dx in (-ch_r * 0.42, ch_r * 0.42):
        if parpadea:
            p.setPen(QPen(QColor(60, 70, 95), max(2.2, ch_r * 0.07)))
            p.drawArc(QRectF(cx + dx - ch_r * 0.2, ojo_y - ch_r * 0.1, ch_r * 0.4, ch_r * 0.2),
                      200 * 16, 140 * 16)
            p.setPen(Qt.NoPen)
        else:
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(cx + dx, ojo_y), ch_r * 0.21, ch_r * 0.26)
            grad = QRadialGradient(cx + dx, ojo_y + ch_r * 0.05, ch_r * 0.22)
            grad.setColorAt(0, QColor("#7dd3fc")); grad.setColorAt(1, QColor("#0ea5e9"))
            p.setBrush(QBrush(grad))
            p.drawEllipse(QPointF(cx + dx, ojo_y + ch_r * 0.02), ch_r * 0.16, ch_r * 0.2)
            p.setBrush(QColor(20, 30, 55))
            p.drawEllipse(QPointF(cx + dx, ojo_y + ch_r * 0.04), ch_r * 0.08, ch_r * 0.1)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(cx + dx + ch_r * 0.06, ojo_y - ch_r * 0.06), ch_r * 0.055, ch_r * 0.065)
            p.setBrush(QColor(255, 255, 255, 160))
            p.drawEllipse(QPointF(cx + dx - ch_r * 0.04, ojo_y + ch_r * 0.09), ch_r * 0.03, ch_r * 0.035)
    # boquita
    p.setPen(QPen(QColor(150, 90, 90), max(1.5, ch_r * 0.04)))
    if durmiendo:
        p.drawArc(QRectF(cx - ch_r * 0.1, ch_y + ch_r * 0.4, ch_r * 0.2, ch_r * 0.15), 0, 180 * 16)
    else:
        p.drawArc(QRectF(cx - ch_r * 0.13, ch_y + ch_r * 0.38, ch_r * 0.26, ch_r * 0.2), 200 * 16, 140 * 16)
    p.setPen(Qt.NoPen)
    # --- audifonos cian (Iroha) ---
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(CYAN), max(3.5, ch_r * 0.13)))
    for dx in (-1, 1):
        p.drawEllipse(QPointF(cx + dx * ch_r * 1.0, ch_y + ch_r * 0.05), ch_r * 0.2, ch_r * 0.28)
    p.drawArc(QRectF(cx - ch_r * 1.0, ch_y - ch_r * 1.08, ch_r * 2.0, ch_r * 1.2), 25 * 16, 130 * 16)
    p.setPen(Qt.NoPen)


# ============================================================ EXPRESIONES (FX)
@dataclass
class _FX:
    tipo: str
    t0: float
    dur: float


class EmocionFX:
    """Capa de expresiones/reacciones procedural, encima del sprite."""
    def __init__(self, clock=time.time):
        self.clock = clock
        self.activos = []
        self.base = None

    def disparar(self, tipo, dur=1.4):
        self.activos.append(_FX(tipo, self.clock(), dur))

    def set_base(self, emocion):
        self.base = emocion

    def dibujar(self, p, rect, now=None):
        now = self.clock() if now is None else now
        if self.base:
            self._uno(p, rect, self.base, (math.sin(now * 2) + 1) / 2)
        for fx in list(self.activos):
            k = (now - fx.t0) / fx.dur
            if k >= 1.0:
                self.activos.remove(fx)
                continue
            self._uno(p, rect, fx.tipo, k)

    def _uno(self, p, r, tipo, k):
        p.save()
        cx = r.x() + r.width() / 2.0
        top = r.y() + r.height() * 0.18
        s = r.width()
        alpha = int(255 * (1 - k)) if tipo != "rubor" else 150
        if tipo == "rubor":
            p.setPen(Qt.NoPen); p.setBrush(QColor(255, 120, 140, 110))
            for dx in (-s * 0.17, s * 0.17):
                p.drawEllipse(QPointF(cx + dx, r.y() + r.height() * 0.46), s * 0.07, s * 0.045)
        elif tipo == "sudor":
            p.setPen(Qt.NoPen); p.setBrush(QColor(120, 200, 255, alpha))
            p.drawEllipse(QPointF(cx + s * 0.28, top + k * s * 0.1), s * 0.05, s * 0.07)
        elif tipo == "enojo":
            p.setPen(QPen(QColor(255, 70, 70, alpha), max(2.0, s * 0.02))); p.setBrush(Qt.NoBrush)
            x, y = cx + s * 0.26, top
            for a in (0, 120, 240):
                ar = math.radians(a)
                p.drawLine(QPointF(x, y), QPointF(x + math.cos(ar) * s * 0.05, y + math.sin(ar) * s * 0.05))
        elif tipo == "estrella":
            self._texto(p, cx, top, "*", s * 0.22, QColor(255, 225, 90, alpha))
        elif tipo == "corazon":
            self._texto(p, cx + s * 0.22, top - k * s * 0.25, "<3", s * 0.16, QColor(255, 110, 150, alpha))
        elif tipo == "dots":
            self._texto(p, cx + s * 0.24, top, "...", s * 0.18, QColor(220, 230, 245, alpha))
        elif tipo == "exclaim":
            esc = 1 + 0.4 * math.sin(k * math.pi)
            self._texto(p, cx + s * 0.22, top, "!", s * 0.26 * esc, QColor(CYAN))
        elif tipo == "duda":
            self._texto(p, cx + s * 0.22, top, "?", s * 0.22, QColor(200, 180, 255, alpha))
        elif tipo == "zzz":
            self._texto(p, cx + s * 0.24, top - k * s * 0.15, "z", s * 0.16, QColor(180, 200, 230, alpha))
        p.restore()

    def _texto(self, p, x, y, txt, px, color):
        f = QFont("Segoe UI", max(6, int(px))); f.setBold(True)
        p.setFont(f); p.setPen(color)
        p.drawText(QRectF(x - px, y - px, px * 3, px * 2), Qt.AlignCenter, txt)


# ============================================================ PERSISTENCIA
class ChibiPersistence:
    def __init__(self, path=None):
        self.path = path or os.path.join(_DATA, "chibi_estado.json")

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self, data):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass


# ============================================================ CONTROLLER (logica)
class ChibiController(QObject):
    """State machine + autonomia. Sin GUI: testeable con un reloj inyectado."""
    repintar = pyqtSignal()
    pedir_abrir = pyqtSignal()
    pedir_mover = pyqtSignal(int, int)

    T_WALK = 20.0
    T_SLEEP = 120.0

    def __init__(self, clock=time.time, parent=None):
        super().__init__(parent)
        self.clock = clock
        self.estado = ChibiState.IDLE
        self._previo = ChibiState.IDLE
        self.frame = 0
        self.cfg = DEFAULT_STATES
        self.fx = EmocionFX(clock=clock)
        self.ultimo_evento = clock()

    def set_estado(self, s, fx=None):
        if s != self.estado:
            if self.estado != ChibiState.REACT:
                self._previo = self.estado
            self.estado = s
            self.frame = 0
        if fx:
            self.fx.disparar(fx)
        self.repintar.emit()

    def interaccion(self):
        self.ultimo_evento = self.clock()
        if self.estado == ChibiState.SLEEP:
            self.set_estado(ChibiState.IDLE, fx="exclaim")

    def on_pensando(self):
        self.interaccion(); self.set_estado(ChibiState.THINK, fx="dots")

    def on_escuchando(self):
        self.interaccion(); self.set_estado(ChibiState.LISTEN)

    def on_respondio(self):
        self.interaccion(); self.set_estado(ChibiState.TALK, fx="estrella")

    def on_idle(self):
        self.set_estado(ChibiState.IDLE)

    def click(self):
        self.interaccion()
        self.set_estado(ChibiState.REACT, fx="exclaim")
        self.fx.set_base("rubor")
        self.pedir_abrir.emit()

    def tick_anim(self):
        a = self.cfg[self.estado]
        self.frame += 1
        if self.frame >= a.frames:
            if a.loop:
                self.frame = 0
            else:
                self.frame = a.frames - 1
                self.set_estado(self._previo)
        self.repintar.emit()

    def tick_idle(self):
        dt = self.clock() - self.ultimo_evento
        if self.estado in (ChibiState.THINK, ChibiState.LISTEN, ChibiState.TALK, ChibiState.REACT):
            return
        if dt > self.T_SLEEP:
            if self.estado != ChibiState.SLEEP:
                self.set_estado(ChibiState.SLEEP, fx="zzz")
        elif dt > self.T_WALK:
            if self.estado == ChibiState.IDLE:
                self.set_estado(ChibiState.WALK)
                self.pedir_mover.emit(random.randint(-220, 220), 0)

    def estado_persistible(self):
        return {"estado": self.estado.value}


# ============================================================ WIDGET (ventana)
class ChibiWidget(QWidget):
    def __init__(self, tema="cyberpunk", size=160):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.resize(size, size)
        self._size = size
        self.tema = tema
        self.persist = ChibiPersistence()
        self.sheet = SpriteSheet(os.path.join(_ASSETS, tema), size, size)
        self.ctrl = ChibiController()
        self.ctrl.repintar.connect(self.update)
        self.ctrl.pedir_mover.connect(self._caminar_hacia)
        self._arrastrando = False
        self._movido = False
        self._offset = QPoint()
        self._cursor_local = QPointF(size / 2, size / 2)
        self._destino = None
        self._restaurar()

    def start(self):
        self._t_anim = QTimer(self); self._t_anim.timeout.connect(self.ctrl.tick_anim); self._t_anim.start(80)
        self._t_idle = QTimer(self); self._t_idle.timeout.connect(self.ctrl.tick_idle); self._t_idle.start(1000)
        self._t_cursor = QTimer(self); self._t_cursor.timeout.connect(self._mirar_cursor); self._t_cursor.start(300)
        self._t_walk = QTimer(self); self._t_walk.timeout.connect(self._paso_caminata); self._t_walk.start(60)
        self.show()

    def _restaurar(self):
        d = self.persist.load()
        pos = d.get("pos")
        if pos and len(pos) == 2:
            self.move(int(pos[0]), int(pos[1]))
        elif QApplication.instance() and QApplication.primaryScreen():
            scr = QApplication.primaryScreen().availableGeometry()
            self.move(scr.right() - self._size - 30, scr.bottom() - self._size - 30)

    def _guardar(self):
        self.persist.save({"pos": [self.x(), self.y()], "tema": self.tema,
                           **self.ctrl.estado_persistible()})

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        bob = math.sin(time.time() * 2) * (self._size * 0.01)
        dest = QRectF(0, bob, self._size, self._size)
        src = self.sheet.frame(self.ctrl.estado, self.ctrl.frame)
        p.drawPixmap(dest, self.sheet.pixmap, QRectF(src))
        if self.ctrl.estado != ChibiState.SLEEP:
            self._ojos_cursor(p)
        self.ctrl.fx.dibujar(p, QRect(0, 0, self._size, self._size))
        p.end()

    def _ojos_cursor(self, p):
        s = self._size
        ex, ey = s / 2, s * 0.44
        dx = max(-1, min(1, (self._cursor_local.x() - ex) / (s * 0.5)))
        dy = max(-1, min(1, (self._cursor_local.y() - ey) / (s * 0.5)))
        p.setBrush(QColor(20, 30, 50)); p.setPen(Qt.NoPen)
        for ox in (-s * 0.11, s * 0.11):
            p.drawEllipse(QPointF(ex + ox + dx * s * 0.015, ey + dy * s * 0.015), s * 0.02, s * 0.025)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._arrastrando = True
            self._offset = e.globalPos() - self.pos()
            self._movido = False

    def mouseMoveEvent(self, e):
        if self._arrastrando:
            self.move(e.globalPos() - self._offset)
            self._movido = True

    def mouseReleaseEvent(self, e):
        if self._arrastrando and not self._movido:
            self.ctrl.click()
        self._arrastrando = False
        self._guardar()

    def _mirar_cursor(self):
        g = QCursor.pos()
        self._cursor_local = QPointF(g.x() - self.x(), g.y() - self.y())
        d = math.hypot(self._cursor_local.x() - self._size / 2, self._cursor_local.y() - self._size / 2)
        if d < self._size * 0.9:
            self.ctrl.interaccion()
        self.update()

    def _caminar_hacia(self, dx, dy):
        self._destino = (self.x() + dx, self.y() + dy)

    def _paso_caminata(self):
        if not self._destino or self.ctrl.estado != ChibiState.WALK:
            return
        tx, ty = self._destino
        x, y = self.x(), self.y()
        paso = 4
        nx = x + max(-paso, min(paso, tx - x))
        ny = y + max(-paso, min(paso, ty - y))
        self.move(nx, ny)
        if abs(nx - tx) < paso and abs(ny - ty) < paso:
            self._destino = None
            self.ctrl.set_estado(ChibiState.IDLE)
            self._guardar()

    def set_tema(self, tema):
        self.tema = tema
        self.sheet = SpriteSheet(os.path.join(_ASSETS, tema), self._size, self._size)
        self.update()

    def closeEvent(self, e):
        self._guardar()
        super().closeEvent(e)


def crear_chibi(tema="cyberpunk", size=160):
    """Fabrica: crea el widget listo para .start(). Requiere un QApplication vivo."""
    return ChibiWidget(tema=tema, size=size)
