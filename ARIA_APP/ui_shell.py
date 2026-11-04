# -*- coding: utf-8 -*-
"""ARIA - Shell cyberpunk-Linux estilo 'rice' (Hyprland-like).

Rework pesado para que parezca un escritorio Linux montado de verdad, no una terminal:
  - fondo animado (wallpaper personalizable + glow que deriva + montanas low-poly)
  - barra tipo polybar arriba
  - TARJETAS-widget glass cohesivas: reloj grande, info de sistema (avatar + uptime +
    shell + CPU/RAM), mini-calendario con el dia marcado
  - chat terminal al centro
  - DOCK abajo con los toggles (AUTO/CUERPO/VOZ)
Frameless (sin apagado), arrastrable. Paleta cyan/violeta. PyQt5, sin deps nuevas.
IMPORTANTE: QSS de Qt NO soporta box-shadow/transform/transition (se evita).
Regla v2 (solo UI local).
"""
import os
import json
import math
import time
import calendar
from datetime import date

try:
    from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF
    from PyQt5.QtGui import (QPainter, QColor, QPen, QBrush, QLinearGradient,
                             QRadialGradient, QPolygonF, QPixmap, QTextCursor, QFont)
    from PyQt5.QtWidgets import (QWidget, QApplication, QVBoxLayout, QHBoxLayout,
                                 QGridLayout, QTextEdit, QLineEdit, QLabel, QPushButton,
                                 QFrame)
    _QT = True
except Exception:
    _QT = False

CYAN = "#38bdf8"
VIOLETA = "#a78bfa"
TEAL = "#2dd4bf"
TXT = "#cfe8ff"
VERDE = "#7dffb0"
MONO = "Consolas"

_DIR = os.path.dirname(os.path.abspath(__file__))
_CFG = os.path.join(_DIR, "data", "fondo.json")


def _cfg_fondo():
    try:
        return json.load(open(_CFG, encoding="utf-8"))
    except Exception:
        return {"wallpaper": "", "animaciones": True, "oscurecer": 0.5}


def _stats():
    try:
        import psutil
        return psutil.cpu_percent(None), psutil.virtual_memory().percent
    except Exception:
        return 0.0, 0.0


if _QT:
    _CARD = ("background:rgba(10,16,34,0.55); border:1px solid rgba(56,189,248,0.30);"
             "border-radius:16px;")

    class _Fondo(QWidget):
        """Fondo rice ANIMADO: wallpaper (ken-burns) + glow que deriva + montanas."""
        def __init__(self, parent=None):
            super().__init__(parent)
            self._t = 0.0
            self._drag = None
            cfg = _cfg_fondo()
            self._anim = bool(cfg.get("animaciones", True))
            self._osc = float(cfg.get("oscurecer", 0.5))
            self._wall = None
            self.set_wallpaper(cfg.get("wallpaper", ""))
            self._timer = QTimer(self); self._timer.timeout.connect(self._tick)
            self._timer.start(33 if self._anim else 1000)

        def set_wallpaper(self, ruta):
            self._wall = None
            if ruta:
                r = ruta if os.path.isabs(ruta) else os.path.join(_DIR, ruta)
                if os.path.isfile(r):
                    px = QPixmap(r)
                    self._wall = px if not px.isNull() else None
            self.update(); return self._wall is not None

        def _tick(self):
            self._t += 0.016; self.update()

        def mousePressEvent(self, e):
            if e.button() == Qt.LeftButton:
                self._drag = e.globalPos() - self.window().frameGeometry().topLeft()

        def mouseMoveEvent(self, e):
            if self._drag is not None:
                self.window().move(e.globalPos() - self._drag)

        def mouseReleaseEvent(self, e):
            self._drag = None

        def paintEvent(self, e):
            p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
            W, H = self.width(), self.height(); t = self._t
            if self._wall is not None:
                self._wallpaper(p, W, H, t)
            else:
                g = QLinearGradient(0, 0, W, H)
                g.setColorAt(0, QColor(16, 14, 40)); g.setColorAt(0.5, QColor(8, 12, 28))
                g.setColorAt(1, QColor(5, 8, 18)); p.fillRect(0, 0, W, H, g)
            d = 20 if self._anim else 0
            for i, (bx, by, rad, col) in enumerate((
                    (0.16, 0.18, 0.42, QColor(56, 189, 248, 55)),
                    (0.86, 0.14, 0.38, QColor(167, 139, 250, 55)),
                    (0.68, 0.9, 0.5, QColor(45, 212, 191, 38)))):
                cx = W * bx + math.sin(t * 0.3 + i) * d
                cy = H * by + math.cos(t * 0.25 + i) * d
                rg = QRadialGradient(cx, cy, W * rad)
                rg.setColorAt(0, col); rg.setColorAt(1, QColor(0, 0, 0, 0))
                p.setBrush(rg); p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(cx, cy), W * rad, W * rad)
            self._montanas(p, W, H, math.sin(t * 0.2) * 12 if self._anim else 0)
            p.setPen(QPen(QColor(56, 189, 248, 6), 1))
            for y in range(0, H, 3):
                p.drawLine(0, y, W, y)
            p.end()

        def _wallpaper(self, p, W, H, t):
            zoom = 1.06 + (0.03 * math.sin(t * 0.15) if self._anim else 0)
            esc = self._wall.scaled(int(W * zoom), int(H * zoom),
                                    Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            px = (W - esc.width()) / 2 + (math.sin(t * 0.1) * 14 if self._anim else 0)
            py = (H - esc.height()) / 2
            p.drawPixmap(int(px), int(py), esc)
            p.fillRect(0, 0, W, H, QColor(6, 8, 20, int(255 * self._osc)))

        def _montanas(self, p, W, H, off):
            base = H * 0.82
            for y0, col, picos, alt in ((base, QColor(56, 189, 248, 22), 7, 70),
                                        (base + 28, QColor(167, 139, 250, 22), 5, 120),
                                        (base + 60, QColor(12, 18, 38, 200), 4, 160)):
                poly = QPolygonF(); poly.append(QPointF(0, H))
                for i in range(picos + 1):
                    x = W * i / picos + off * (1 - (y0 - base) / 100.0)
                    poly.append(QPointF(x, y0 - abs(math.sin(i * 1.7 + y0)) * alt))
                poly.append(QPointF(W, H))
                p.setBrush(QBrush(col)); p.setPen(Qt.NoPen); p.drawPolygon(poly)

    # ---------------- widgets de sistema (barras pintadas) ----------------
    class _Barra(QWidget):
        def __init__(self, label, color):
            super().__init__(); self.setFixedHeight(16); self._v = 0.0
            self._label = label; self._color = QColor(color)
        def set_v(self, v): self._v = max(0.0, min(1.0, v)); self.update()
        def paintEvent(self, e):
            p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
            W, H = self.width(), self.height()
            p.setPen(QColor(TXT)); f = QFont(MONO, 8); p.setFont(f)
            p.drawText(0, 0, 44, H, Qt.AlignVCenter, self._label)
            x = 48; bw = W - x
            p.setBrush(QColor(255, 255, 255, 22)); p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(x, H / 2 - 4, bw, 8), 4, 4)
            p.setBrush(self._color)
            p.drawRoundedRect(QRectF(x, H / 2 - 4, bw * self._v, 8), 4, 4)
            p.end()

    def _tarjeta():
        f = QFrame(); f.setStyleSheet("QFrame{%s}" % _CARD); return f

    class Shell(QWidget):
        def __init__(self, responder=None, w=940, h=600):
            super().__init__(None)
            self.responder = responder
            self.toggles = {"autonomia": True, "cuerpo": "nucleo", "voz": False}
            self.setWindowFlags(Qt.FramelessWindowHint)
            self.resize(w, h); self.setWindowTitle("ARIA")
            self._fondo = _Fondo(self)
            self._build(); self._reloj()

        def showEvent(self, e):
            super().showEvent(e)
            if not getattr(self, "_blur_ok", False):
                self._blur_ok = True
                try:
                    import pywinstyles           # blur nativo de Windows (opcional, liviano)
                    pywinstyles.apply_style(self, "acrylic")
                except Exception:
                    pass

        def resizeEvent(self, e):
            self._fondo.setGeometry(0, 0, self.width(), self.height())

        # --------- construccion ---------
        def _build(self):
            root = QVBoxLayout(self); root.setContentsMargins(18, 12, 18, 12); root.setSpacing(12)
            root.addLayout(self._polybar())
            fila = QHBoxLayout(); fila.setSpacing(12)
            fila.addLayout(self._centro(), 1)
            fila.addLayout(self._widgets(), 0)
            root.addLayout(fila, 1)
            root.addLayout(self._dock())
            self._pintar_toggles()

        def _polybar(self):
            bar = QHBoxLayout(); bar.setSpacing(10)
            ws = QLabel("● 1  2  3  4"); ws.setStyleSheet("color:%s;font:700 11px '%s';letter-spacing:2px;" % (CYAN, MONO))
            tit = QLabel("ARIA // SYSTEM"); tit.setStyleSheet("color:%s;font:700 12px '%s';letter-spacing:3px;" % (TXT, MONO))
            self._lbl_sys = QLabel(""); self._lbl_sys.setStyleSheet("color:%s;font:11px '%s';" % (TEAL, MONO))
            self._lbl_rel = QLabel(""); self._lbl_rel.setStyleSheet("color:%s;font:700 12px '%s';" % (CYAN, MONO))
            bar.addWidget(ws); bar.addStretch(1); bar.addWidget(tit); bar.addStretch(1)
            bar.addWidget(self._lbl_sys); bar.addSpacing(14); bar.addWidget(self._lbl_rel)
            return bar

        def _centro(self):
            col = QVBoxLayout(); col.setSpacing(10)
            self.log = QTextEdit(); self.log.setReadOnly(True)
            self.log.setStyleSheet("QTextEdit{%s color:%s;font:12px '%s';padding:14px;}" % (_CARD, TXT, MONO))
            col.addWidget(self.log, 1)
            self._linea("ARIA en linea · siempre presente", "sys")
            fila = QHBoxLayout(); fila.setSpacing(8)
            pr = QLabel("root@aria:~#"); pr.setStyleSheet("color:%s;font:700 12px '%s';" % (TEAL, MONO))
            self.entrada = QLineEdit(); self.entrada.setPlaceholderText("escribe y Enter...")
            self.entrada.setStyleSheet(
                "QLineEdit{background:rgba(2,6,14,0.7);border:1px solid rgba(56,189,248,0.5);"
                "border-radius:10px;color:%s;font:12px '%s';padding:10px;}"
                "QLineEdit:focus{border:1px solid %s;}" % (TXT, MONO, CYAN))
            self.entrada.returnPressed.connect(self._enviar)
            fila.addWidget(pr); fila.addWidget(self.entrada, 1)
            col.addLayout(fila)
            return col

        def _widgets(self):
            col = QVBoxLayout(); col.setSpacing(12)
            col.addWidget(self._card_reloj())
            col.addWidget(self._card_sistema())
            col.addWidget(self._card_calendario())
            col.addStretch(1)
            return col

        def _card_reloj(self):
            c = _tarjeta(); c.setFixedWidth(240)
            lay = QVBoxLayout(c); lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(2)
            self._reloj_big = QLabel("--:--"); self._reloj_big.setStyleSheet("color:%s;font:700 34px '%s';" % (CYAN, MONO))
            self._fecha_big = QLabel(""); self._fecha_big.setStyleSheet("color:%s;font:11px '%s';" % (TXT, MONO))
            lay.addWidget(self._reloj_big); lay.addWidget(self._fecha_big)
            return c

        def _card_sistema(self):
            c = _tarjeta(); c.setFixedWidth(240)
            lay = QVBoxLayout(c); lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(8)
            top = QHBoxLayout()
            av = QLabel("A"); av.setFixedSize(40, 40); av.setAlignment(Qt.AlignCenter)
            av.setStyleSheet("background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 %s,stop:1 %s);"
                             "color:#06111f;border-radius:20px;font:700 20px '%s';" % (CYAN, VIOLETA, MONO))
            nom = QVBoxLayout(); nom.setSpacing(0)
            n1 = QLabel("aria@raiden"); n1.setStyleSheet("color:%s;font:700 12px '%s';" % (TXT, MONO))
            n2 = QLabel("cyberpunk-linux"); n2.setStyleSheet("color:%s;font:9px '%s';" % (TEAL, MONO))
            nom.addWidget(n1); nom.addWidget(n2)
            top.addWidget(av); top.addSpacing(8); top.addLayout(nom); top.addStretch(1)
            lay.addLayout(top)
            self._up = QLabel(""); self._up.setStyleSheet("color:%s;font:9px '%s';" % (TXT, MONO))
            lay.addWidget(self._up)
            self._bcpu = _Barra("CPU", CYAN); self._bram = _Barra("RAM", VIOLETA)
            lay.addWidget(self._bcpu); lay.addWidget(self._bram)
            self._t0 = time.time()
            return c

        def _card_calendario(self):
            c = _tarjeta(); c.setFixedWidth(240)
            lay = QVBoxLayout(c); lay.setContentsMargins(14, 10, 14, 12); lay.setSpacing(4)
            hoy = date.today()
            tit = QLabel(hoy.strftime("%B %Y").capitalize())
            tit.setStyleSheet("color:%s;font:700 12px '%s';" % (CYAN, MONO))
            lay.addWidget(tit)
            grid = QGridLayout(); grid.setSpacing(2)
            for i, d in enumerate(["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"]):
                h = QLabel(d); h.setAlignment(Qt.AlignCenter)
                h.setStyleSheet("color:%s;font:8px '%s';" % (TEAL, MONO)); grid.addWidget(h, 0, i)
            cal = calendar.Calendar(firstweekday=0)
            r = 1
            for semana in cal.monthdayscalendar(hoy.year, hoy.month):
                for i, dia in enumerate(semana):
                    if dia == 0:
                        continue
                    lab = QLabel(str(dia)); lab.setAlignment(Qt.AlignCenter)
                    if dia == hoy.day:
                        lab.setStyleSheet("background:%s;color:#06111f;border-radius:9px;"
                                          "font:700 10px '%s';padding:1px;" % (CYAN, MONO))
                    else:
                        lab.setStyleSheet("color:%s;font:10px '%s';" % (TXT, MONO))
                    grid.addWidget(lab, r, i)
                r += 1
            lay.addLayout(grid)
            return c

        def _dock(self):
            wrap = QHBoxLayout(); wrap.addStretch(1)
            dock = QFrame(); dock.setStyleSheet("QFrame{%s}" % _CARD)
            inner = QHBoxLayout(dock); inner.setContentsMargins(10, 6, 10, 6); inner.setSpacing(8)
            self._btn = {}
            for key in ("autonomia", "cuerpo", "voz"):
                b = QPushButton(); b.setFixedHeight(34)
                b.clicked.connect(lambda _, k=key: self._toggle(k))
                self._btn[key] = b; inner.addWidget(b)
            wrap.addWidget(dock); wrap.addStretch(1)
            return wrap

        # --------- logica ---------
        def _toggle(self, key):
            if key == "cuerpo":
                self.toggles["cuerpo"] = "avatar" if self.toggles["cuerpo"] == "nucleo" else "nucleo"
                self._linea("cuerpo -> %s" % self.toggles["cuerpo"], "sys")
            else:
                self.toggles[key] = not self.toggles[key]
                self._linea("%s -> %s" % (key, "ON" if self.toggles[key] else "OFF"), "sys")
            self._pintar_toggles()

        def _pintar_toggles(self):
            for key, b in self._btn.items():
                val = self.toggles[key]
                on = (val is True) or (key == "cuerpo")
                col = CYAN if on else "#5b7089"
                b.setText("CUERPO:%s" % val if key == "cuerpo" else "%s:%s" % (key.upper()[:4], "ON" if val else "OFF"))
                b.setStyleSheet(
                    "QPushButton{background:rgba(56,189,248,%d);color:%s;border:1px solid %s;"
                    "border-radius:9px;font:700 11px '%s';padding:6px 12px;}"
                    "QPushButton:hover{background:rgba(56,189,248,60);}" % (40 if on else 16, col, col, MONO))

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
                self._lbl_rel.setText(time.strftime("%H:%M:%S"))
                cpu, ram = _stats()
                self._lbl_sys.setText("CPU %2.0f%%  RAM %2.0f%%" % (cpu, ram))
                self._reloj_big.setText(time.strftime("%H:%M"))
                self._fecha_big.setText(time.strftime("%A, %d %b").capitalize())
                self._bcpu.set_v(cpu / 100.0); self._bram.set_v(ram / 100.0)
                mins = int((time.time() - self._t0) / 60)
                self._up.setText("uptime %dm · shell: aria · wm: nucleo" % mins)
            self._timer = QTimer(self); self._timer.timeout.connect(tick); self._timer.start(1000); tick()

    def crear_shell(responder=None, w=940, h=600):
        return Shell(responder, w, h)
else:
    def crear_shell(responder=None, w=940, h=600):
        return {"error": "PyQt5 no disponible"}


if __name__ == "__main__":
    app = QApplication([])
    s = crear_shell(lambda t: "recibido: " + t); s.show(); app.exec_()
