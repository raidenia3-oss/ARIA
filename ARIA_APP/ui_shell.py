# -*- coding: utf-8 -*-
"""ARIA - Shell cyberpunk-Linux (ventana principal, estetica 'riced' animada).

Inspirado en Hyprland/unixporn: WALLPAPER personalizable (imagen propia) con ANIMACION
(ken-burns + parallax), capas de glow ambiental que derivan, montanas low-poly, barra
tipo polybar y chat terminal. SIN boton de apagado: ARIA siempre esta (ventana frameless,
arrastrable). Casi sin botones: 3 toggles (autonomia, cuerpo, voz); el resto es autonomo.

Wallpaper configurable en data/fondo.json:
  {"wallpaper": "data/wallpapers/mi.jpg", "animaciones": true, "oscurecer": 0.45}
Cambialo en vivo con shell._fondo.set_wallpaper(ruta). Si no hay imagen, fondo procedural.

Paleta TokyoNight/ARIA: navy + cyan (#38bdf8) + violeta. PyQt5, sin deps nuevas.
Regla v2 (solo UI local, sin red).
"""
import os
import json
import math
import time

try:
    from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF
    from PyQt5.QtGui import (QPainter, QColor, QPen, QBrush, QLinearGradient,
                             QRadialGradient, QPolygonF, QPixmap, QTextCursor)
    from PyQt5.QtWidgets import (QWidget, QApplication, QVBoxLayout, QHBoxLayout,
                                 QTextEdit, QLineEdit, QLabel, QPushButton)
    _QT = True
except Exception:
    _QT = False

CYAN = "#38bdf8"
VIOLETA = "#a78bfa"
TEAL = "#2dd4bf"
TXT = "#cfe8ff"
VERDE = "#7dffb0"

_DIR = os.path.dirname(os.path.abspath(__file__))
_CFG = os.path.join(_DIR, "data", "fondo.json")


def _cfg_fondo():
    try:
        return json.load(open(_CFG, encoding="utf-8"))
    except Exception:
        return {"wallpaper": "", "animaciones": True, "oscurecer": 0.45}


def _stats():
    try:
        import psutil
        return psutil.cpu_percent(None), psutil.virtual_memory().percent
    except Exception:
        return 0.0, 0.0


def _neofetch():
    cpu, ram = _stats()
    return [
        "        /\\\\",
        "       /  \\\\     <b>aria</b>@<b>raiden</b>",
        "      / /\\\\ \\\\    ----------------",
        "     / ____ \\\\   OS: ARIA Shell (cyberpunk-linux)",
        "    /_/    \\\\_\\\\  kernel: aria-core",
        "               shell: root@aria",
        "               cpu: Ryzen 7 5700G",
        "               mem: %2.0f%% en uso" % ram,
    ]


if _QT:
    class _Fondo(QWidget):
        """Fondo 'riced' ANIMADO: wallpaper (ken-burns) + glow que deriva + montanas
        con parallax + grid/scanlines. Timer propio ~30fps. Arrastra la ventana."""
        def __init__(self, parent=None):
            super().__init__(parent)
            self._t = 0.0
            self._drag = None
            cfg = _cfg_fondo()
            self._anim = bool(cfg.get("animaciones", True))
            self._oscurecer = float(cfg.get("oscurecer", 0.45))
            self._wall = None
            self.set_wallpaper(cfg.get("wallpaper", ""))
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(33 if self._anim else 1000)

        def set_wallpaper(self, ruta):
            """Carga una imagen como fondo (o la quita si vacio). Personalizable."""
            self._wall = None
            if ruta:
                r = ruta if os.path.isabs(ruta) else os.path.join(_DIR, ruta)
                if os.path.isfile(r):
                    px = QPixmap(r)
                    if not px.isNull():
                        self._wall = px
            self.update()
            return self._wall is not None

        def _tick(self):
            self._t += 0.016
            self.update()

        # ---- arrastrar la ventana desde el fondo (no hay barra del SO) ----
        def mousePressEvent(self, e):
            if e.button() == Qt.LeftButton:
                self._drag = e.globalPos() - self.window().frameGeometry().topLeft()

        def mouseMoveEvent(self, e):
            if self._drag is not None:
                self.window().move(e.globalPos() - self._drag)

        def mouseReleaseEvent(self, e):
            self._drag = None

        def paintEvent(self, e):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            W, H = self.width(), self.height()
            t = self._t
            if self._wall is not None:
                self._dibujar_wallpaper(p, W, H, t)
            else:
                g = QLinearGradient(0, 0, W, H)
                g.setColorAt(0, QColor(13, 18, 38)); g.setColorAt(0.5, QColor(8, 12, 26))
                g.setColorAt(1, QColor(5, 8, 18))
                p.fillRect(0, 0, W, H, g)
            # glow ambiental que DERIVA (animado)
            d = 18 if self._anim else 0
            for i, (bx, by, rad, col) in enumerate((
                    (0.18, 0.2, 0.42, QColor(56, 189, 248, 50)),
                    (0.85, 0.15, 0.36, QColor(167, 139, 250, 44)),
                    (0.7, 0.85, 0.46, QColor(45, 212, 191, 32)))):
                cx = W * bx + math.sin(t * 0.3 + i) * d
                cy = H * by + math.cos(t * 0.25 + i) * d
                rg = QRadialGradient(cx, cy, W * rad)
                rg.setColorAt(0, col); rg.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(rg); p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(cx, cy), W * rad, W * rad)
            # grid + montanas (parallax) + scanlines + esquinas
            p.setPen(QPen(QColor(56, 189, 248, 10), 1))
            for x in range(0, W, 38): p.drawLine(x, 0, x, H)
            for y in range(0, H, 38): p.drawLine(0, y, W, y)
            self._montanas(p, W, H, math.sin(t * 0.2) * 10 if self._anim else 0)
            p.setPen(QPen(QColor(56, 189, 248, 7), 1))
            for y in range(0, H, 3): p.drawLine(0, y, W, y)
            p.setPen(QPen(QColor(CYAN), 2)); L = 22
            for (x, y, dx, dy) in ((10, 10, 1, 1), (W - 10, 10, -1, 1),
                                   (10, H - 10, 1, -1), (W - 10, H - 10, -1, -1)):
                p.drawLine(x, y, x + dx * L, y); p.drawLine(x, y, x, y + dy * L)
            p.end()

        def _dibujar_wallpaper(self, p, W, H, t):
            """Dibuja la imagen cubriendo el area, con ken-burns (zoom/pan lento) y
            un velo oscuro para que el texto se lea. 'Mejora' cualquier imagen."""
            zoom = 1.06 + (0.03 * math.sin(t * 0.15) if self._anim else 0)
            panx = math.sin(t * 0.1) * 14 if self._anim else 0
            pany = math.cos(t * 0.12) * 10 if self._anim else 0
            pw, ph = int(W * zoom), int(H * zoom)
            esc = self._wall.scaled(pw, ph, Qt.KeepAspectRatioByExpanding,
                                    Qt.SmoothTransformation)
            x = (W - esc.width()) / 2 + panx
            y = (H - esc.height()) / 2 + pany
            p.drawPixmap(int(x), int(y), esc)
            p.fillRect(0, 0, W, H, QColor(5, 8, 18, int(255 * self._oscurecer)))

        def _montanas(self, p, W, H, off):
            base = H * 0.78
            for y0, col, picos, alt in ((base, QColor(56, 189, 248, 26), 7, 90),
                                        (base + 34, QColor(167, 139, 250, 24), 5, 140),
                                        (base + 70, QColor(13, 20, 40, 210), 4, 180)):
                poly = QPolygonF(); poly.append(QPointF(0, H))
                for i in range(picos + 1):
                    x = W * i / picos + off * (1 - (y0 - base) / 120.0)
                    y = y0 - abs(math.sin(i * 1.7 + y0)) * alt
                    poly.append(QPointF(x, y))
                poly.append(QPointF(W, H))
                p.setBrush(QBrush(col)); p.setPen(Qt.NoPen); p.drawPolygon(poly)


    class Shell(QWidget):
        def __init__(self, responder=None, w=760, h=540):
            super().__init__(None)
            self.responder = responder
            self.toggles = {"autonomia": True, "cuerpo": "nucleo", "voz": False}
            self.setWindowFlags(Qt.FramelessWindowHint)   # SIN barra del SO = sin apagado/X
            self.resize(w, h)
            self.setWindowTitle("ARIA")
            self._fondo = _Fondo(self)
            self._build()
            self._reloj()

        def resizeEvent(self, e):
            self._fondo.setGeometry(0, 0, self.width(), self.height())

        def _build(self):
            mono = "Consolas"
            root = QVBoxLayout(self); root.setContentsMargins(16, 10, 16, 14); root.setSpacing(8)
            bar = QHBoxLayout(); bar.setSpacing(10)
            ws = QLabel("1 2 3 4"); ws.setStyleSheet(
                "color:%s; font:700 11px '%s'; letter-spacing:4px;" % (CYAN, mono))
            titulo = QLabel("ARIA // SYSTEM SHELL"); titulo.setStyleSheet(
                "color:%s; font:700 12px '%s'; letter-spacing:2px;" % (TXT, mono))
            self._lbl_sys = QLabel(""); self._lbl_sys.setStyleSheet("color:%s; font:11px '%s';" % (TEAL, mono))
            self._lbl_reloj = QLabel(""); self._lbl_reloj.setStyleSheet("color:%s; font:700 12px '%s';" % (CYAN, mono))
            bar.addWidget(ws); bar.addStretch(1); bar.addWidget(titulo)
            bar.addStretch(1); bar.addWidget(self._lbl_sys); bar.addSpacing(12); bar.addWidget(self._lbl_reloj)
            root.addLayout(bar)

            self.log = QTextEdit(); self.log.setReadOnly(True)
            self.log.setStyleSheet(
                "QTextEdit{background:rgba(2,6,14,140); border:1px solid rgba(56,189,248,55);"
                "border-radius:10px; color:%s; font:12px '%s'; padding:12px;}" % (TXT, mono))
            root.addWidget(self.log, 1)
            self._bienvenida()

            fila = QHBoxLayout(); fila.setSpacing(8)
            self._btn = {}
            for key in ("autonomia", "cuerpo", "voz"):
                b = QPushButton(); b.setFixedHeight(34)
                b.clicked.connect(lambda _, k=key: self._toggle(k))
                self._btn[key] = b; fila.addWidget(b)
            prompt = QLabel("root@aria:~#"); prompt.setStyleSheet("color:%s; font:700 12px '%s';" % (TEAL, mono))
            self.entrada = QLineEdit(); self.entrada.setPlaceholderText("escribe y Enter...")
            self.entrada.setStyleSheet(
                "QLineEdit{background:rgba(2,6,14,200); border:1px solid rgba(56,189,248,90);"
                "border-radius:6px; color:%s; font:12px '%s'; padding:8px;}"
                "QLineEdit:focus{border:1px solid %s;}" % (TXT, mono, CYAN))
            self.entrada.returnPressed.connect(self._enviar)
            fila.addSpacing(6); fila.addWidget(prompt); fila.addWidget(self.entrada, 1)
            root.addLayout(fila); self._pintar_toggles()

        def _toggle(self, key):
            if key == "cuerpo":
                self.toggles["cuerpo"] = "avatar" if self.toggles["cuerpo"] == "nucleo" else "nucleo"
                self._linea("cuerpo -> %s" % self.toggles["cuerpo"], "sys")
            else:
                self.toggles[key] = not self.toggles[key]
                self._linea("%s -> %s" % (key, "ON" if self.toggles[key] else "OFF"), "sys")
            self._pintar_toggles()

        def _pintar_toggles(self):
            mono = "Consolas"
            for key, b in self._btn.items():
                val = self.toggles[key]
                on = (val is True) or (key == "cuerpo")
                col = CYAN if on else "#5b7089"
                if key == "cuerpo":
                    b.setText("CUERPO:%s" % ("nucleo" if val == "nucleo" else "avatar"))
                else:
                    b.setText("%s:%s" % (key.upper()[:4], "ON" if val else "OFF"))
                b.setStyleSheet(
                    "QPushButton{background:rgba(56,189,248,%d); color:%s; border:1px solid %s;"
                    "border-radius:6px; font:700 11px '%s'; padding:6px 10px;}"
                    "QPushButton:hover{background:rgba(56,189,248,55);}"
                    % (34 if on else 14, col, col, mono))

        def _bienvenida(self):
            for ln in _neofetch():
                self.log.append('<span style="color:%s; font-family:Consolas">%s</span>' % (VERDE, ln))
            self.log.append("")
            self._linea("cerebro local listo · autonomia ACTIVA · siempre presente", "sys")

        def _linea(self, texto, quien="aria"):
            col = {"user": CYAN, "aria": TXT, "sys": VERDE}.get(quien, TXT)
            pref = {"user": "> ", "aria": "ARIA: ", "sys": "· "}.get(quien, "")
            self.log.append('<span style="color:%s">%s%s</span>' % (col, pref, texto))
            self.log.moveCursor(QTextCursor.End)

        def _enviar(self):
            t = self.entrada.text().strip()
            if not t:
                return
            self.entrada.clear(); self._linea(t, "user")
            if callable(self.responder):
                try:
                    r = self.responder(t)
                    if isinstance(r, dict):
                        r = r.get("response") or r.get("text") or str(r)
                except Exception as exc:
                    r = "(error: %s)" % exc
            else:
                r = "(sin cerebro conectado)"
            self._linea(str(r), "aria")

        def _reloj(self):
            def tick():
                self._lbl_reloj.setText(time.strftime("%H:%M:%S"))
                cpu, ram = _stats()
                self._lbl_sys.setText("  CPU %2.0f%%   RAM %2.0f%%   net ·" % (cpu, ram))
            self._timer = QTimer(self); self._timer.timeout.connect(tick); self._timer.start(1000); tick()


    def crear_shell(responder=None, w=760, h=540):
        return Shell(responder, w, h)
else:
    def crear_shell(responder=None, w=760, h=540):
        return {"error": "PyQt5 no disponible"}


if __name__ == "__main__":
    app = QApplication([])
    s = crear_shell(lambda t: "recibido: " + t)
    s.show()
    app.exec_()
