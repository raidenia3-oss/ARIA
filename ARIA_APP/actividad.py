# -*- coding: utf-8 -*-
"""ARIA - Actividad de hoy (idea robada de Zoey: el nucleo con tarjetas orbitando).

Zoey muestra un nucleo central con "28 trabajos hechos hoy" y tarjetas (Calls, Posts,
Leads, Search) orbitando. Robamos ESA idea de UX: un nucleo con el conteo de lo que
ARIA hizo/recolecto HOY y tarjetas girando alrededor. Lee de lo que ARIA ya registra:
  - noticias.py   -> lo que recolecto del mundo
  - experiencia   -> lecciones que aprendio
  - auditoria     -> acciones (sobre todo las autonomas)
  - resurgir      -> el recuerdo del dia

La LOGICA (recopilar, clasificar, filtrar por hoy, resumir) es PURA y testeable con
datos inyectados. La parte visual (Actividad) usa solo QPainter + 1 timer de giro.
Regla v2: UI local, sin servidores. pywinstyles (blur) opcional. No roba foco ni overlay.
"""
import os
import time

# colores por tipo de actividad (paleta ARIA)
COLORES = {
    "noticia": "#2dd4bf",   # vigia / mundo
    "leccion": "#fbbf24",   # aprendio
    "accion":  "#38bdf8",   # hizo algo
    "auto":    "#f87171",   # accion autonoma (ojo)
    "recuerdo": "#a78bfa",  # resurgir
}
ICONO = {"noticia": "N", "leccion": "L", "accion": "A", "auto": "!", "recuerdo": "R"}


# ======================================================================= LOGICA PURA

def _es_hoy(fecha, hoy):
    """True si la fecha ('YYYY-MM-DD...' o 'YYYY-MM-DD HH:MM...') es de hoy. Puro."""
    return bool(fecha) and str(fecha)[:10] == hoy


def recopilar_de(noticias=None, lecciones=None, acciones=None, recuerdo=None,
                 cache_fecha=None, hoy=None, maximo=7):
    """Une todas las fuentes en una lista de tarjetas de actividad. PURA.

    noticias   = [{titulo, fuente, url?}, ...]   (de noticias.cache())
    cache_fecha= fecha del cache de noticias ('YYYY-MM-DD HH:MM')
    lecciones  = [{fecha, resultado, leccion, tema}, ...]  (de experiencia.leer())
    acciones   = [{fecha, tipo, accion, autonomo}, ...]    (de auditoria.leer())
    recuerdo   = tarjeta de resurgir (dict con texto/fuente) o None
    Devuelve [{tipo, icono, titulo, sub, color, url}] mas reciente primero (hasta maximo).
    """
    items = []
    # noticias: se consideran de hoy si el cache es de hoy
    if noticias and _es_hoy(cache_fecha, hoy):
        for n in noticias:
            items.append({"tipo": "noticia", "icono": ICONO["noticia"],
                          "titulo": (n.get("titulo") or "")[:70],
                          "sub": n.get("fuente") or "", "color": COLORES["noticia"],
                          "url": n.get("url") or "", "_orden": 2})
    # lecciones de hoy
    for l in (lecciones or []):
        if _es_hoy(l.get("fecha"), hoy):
            items.append({"tipo": "leccion", "icono": ICONO["leccion"],
                          "titulo": (l.get("leccion") or "")[:70],
                          "sub": l.get("tema") or l.get("resultado") or "",
                          "color": COLORES["leccion"], "url": "", "_orden": 3})
    # acciones de hoy (autonomas resaltadas)
    for a in (acciones or []):
        if _es_hoy(a.get("fecha"), hoy):
            auto = bool(a.get("autonomo"))
            tipo = "auto" if auto else "accion"
            items.append({"tipo": tipo, "icono": ICONO[tipo],
                          "titulo": (a.get("accion") or "")[:70],
                          "sub": ("autonoma" if auto else "") or a.get("tipo") or "",
                          "color": COLORES[tipo], "url": "", "_orden": 1 if auto else 4})
    # recuerdo del dia (resurgir)
    if recuerdo and recuerdo.get("texto"):
        items.append({"tipo": "recuerdo", "icono": ICONO["recuerdo"],
                      "titulo": ("Recuerda: " + recuerdo["texto"])[:70],
                      "sub": recuerdo.get("fuente") or "", "color": COLORES["recuerdo"],
                      "url": "", "_orden": 2})
    # orden: autonomas y novedades primero; recortar
    items.sort(key=lambda x: x.get("_orden", 9))
    for x in items:
        x.pop("_orden", None)
    return items[:maximo]


def resumen(items):
    """Conteo por tipo + total. Puro."""
    por = {}
    for x in items or []:
        por[x["tipo"]] = por.get(x["tipo"], 0) + 1
    return {"total": len(items or []), "por_tipo": por}


# ====================================================================== PARTE IMPURA

def _hoy():
    return time.strftime("%Y-%m-%d")


def recopilar(maximo=7):
    """Lee las fuentes reales de ARIA (todas guardadas) y arma la actividad de hoy."""
    hoy = _hoy()
    noticias, cache_fecha, lecciones, acciones, recuerdo = [], None, [], [], None
    try:
        import noticias as _n
        c = _n.cache()
        noticias = c.get("noticias", []); cache_fecha = c.get("fecha")
    except Exception:
        pass
    try:
        import experiencia as _e
        lecciones = _e.leer(n=10)
    except Exception:
        pass
    try:
        import auditoria as _a
        acciones = _a.leer(n=15)
    except Exception:
        pass
    try:
        import resurgir as _r
        t = _r.resurgir(marcar=False)
        if not t.get("vacio"):
            recuerdo = t
    except Exception:
        pass
    return recopilar_de(noticias, lecciones, acciones, recuerdo,
                        cache_fecha=cache_fecha, hoy=hoy, maximo=maximo)


# ====================================================================== PARTE VISUAL
import math

try:
    from PyQt5.QtCore import (Qt, QTimer, QPoint, QPointF, QRectF, QPropertyAnimation,
                              QEasingCurve)
    from PyQt5.QtGui import QPainter, QColor, QPen, QRadialGradient, QFont
    from PyQt5.QtWidgets import QWidget, QApplication
    import webbrowser
    _QT = True
except Exception:
    _QT = False


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


if _QT:
    class Actividad(QWidget):
        """Nucleo central con el conteo de HOY y tarjetas orbitando (idea Zoey)."""
        def __init__(self, size=420):
            super().__init__(None)
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnBottomHint | Qt.Tool)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)   # no roba foco, no overlay
            self.resize(size, size)
            self._s = size
            self._items = []
            self._rects = []        # (rect, url) para click
            self._t = 0.0
            self._drag = None
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)

        def start(self, fps=20):
            self.refrescar()
            self._timer.start(int(1000 / fps))
            scr = QApplication.primaryScreen().availableGeometry() if QApplication.instance() else None
            if scr:
                self.move(scr.center().x() - self._s // 2, scr.center().y() - self._s // 2)
            self.show()

        def _tick(self):
            self._t += 0.03
            self.update()

        def showEvent(self, e):
            super().showEvent(e)
            if not getattr(self, "_blur_ok", False):
                self._blur_ok = True
                try:
                    import pywinstyles
                    pywinstyles.apply_style(self, "acrylic")
                except Exception:
                    pass

        def refrescar(self):
            try:
                self._items = recopilar()
            except Exception:
                self._items = []
            self.update()
            return self._items

        def set_items(self, items):
            """Inyectar actividad (para pruebas o fuentes externas)."""
            self._items = list(items or [])
            self.update()

        # -- panel deslizable (como el selector/bandeja) --
        def deslizar_entrada(self, margen=16):
            scr = QApplication.primaryScreen().availableGeometry()
            y = scr.center().y() - self._s // 2
            fuera = QPoint(scr.right(), y)
            dentro = QPoint(scr.right() - self._s - margen, y)
            self.move(fuera); self.show()
            self._slide = QPropertyAnimation(self, b"pos")
            self._slide.setDuration(320); self._slide.setStartValue(fuera)
            self._slide.setEndValue(dentro); self._slide.setEasingCurve(QEasingCurve.OutCubic)
            self._slide.start()

        def deslizar_salida(self):
            scr = QApplication.primaryScreen().availableGeometry()
            self._slide = QPropertyAnimation(self, b"pos")
            self._slide.setDuration(240); self._slide.setStartValue(self.pos())
            self._slide.setEndValue(QPoint(scr.right(), self.pos().y()))
            self._slide.setEasingCurve(QEasingCurve.InCubic)
            self._slide.finished.connect(self.hide)
            self._slide.start()

        def mousePressEvent(self, e):
            if e.button() != Qt.LeftButton:
                return
            # click en una tarjeta con url -> abre; si no, arrastra
            for rect, url in self._rects:
                if rect.contains(QPointF(e.pos())):
                    if url:
                        try:
                            webbrowser.open(url)
                        except Exception:
                            pass
                        return
            self._drag = e.globalPos() - self.pos()

        def mouseMoveEvent(self, e):
            if self._drag is not None:
                self.move(e.globalPos() - self._drag)

        def mouseReleaseEvent(self, e):
            self._drag = None

        # -- pintura --
        def paintEvent(self, e):
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            S = self._s
            c = S / 2.0
            self._rects = []
            self._centro(p, S, c)
            self._orbitas(p, S, c)
            self._tarjetas(p, S, c)
            p.end()

        def _centro(self, p, S, c):
            # orbe + conteo del dia
            r = S * 0.13
            g = QRadialGradient(c, c, r * 1.6)
            g.setColorAt(0, QColor(56, 189, 248, 210))
            g.setColorAt(0.7, QColor(56, 189, 248, 60))
            g.setColorAt(1, QColor(56, 189, 248, 0))
            p.setBrush(g); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(c, c), r * 1.6, r * 1.6)
            n = len(self._items)
            p.setPen(QColor(255, 255, 255, 245))
            fn = QFont("Consolas", 26); fn.setBold(True); p.setFont(fn)
            p.drawText(QRectF(0, c - 28, S, 40), Qt.AlignCenter, str(n))
            fl = QFont("Consolas", 9); fl.setLetterSpacing(QFont.AbsoluteSpacing, 2)
            p.setFont(fl); p.setPen(QColor(205, 232, 255, 220))
            p.drawText(QRectF(0, c + 10, S, 18), Qt.AlignCenter,
                       "COSAS HOY" if n != 1 else "COSA HOY")

        def _orbitas(self, p, S, c):
            p.setBrush(Qt.NoBrush)
            for rr in (S * 0.26, S * 0.37):
                p.setPen(QPen(QColor(90, 140, 190, 40), 1.0))
                p.drawEllipse(QRectF(c - rr, c - rr * 0.74, 2 * rr, 2 * rr * 0.74))

        def _tarjetas(self, p, S, c):
            n = max(1, len(self._items))
            rx, ry = S * 0.37, S * 0.37 * 0.74     # orbita eliptica (cabe con margen)
            w, h = S * 0.26, 30
            for i, it in enumerate(self._items):
                ang = self._t * 0.25 + (2 * math.pi * i / n)
                x = c + rx * math.cos(ang)
                y = c + ry * math.sin(ang)
                rect = QRectF(x - w / 2, y - h / 2, w, h)
                self._rects.append((rect, it.get("url", "")))
                col = _rgb(it.get("color", "#38bdf8"))
                # tarjeta
                p.setBrush(QColor(10, 16, 34, 220))
                p.setPen(QPen(QColor(col[0], col[1], col[2], 160), 1.2))
                p.drawRoundedRect(rect, 8, 8)
                # punto de color + icono
                p.setBrush(QColor(col[0], col[1], col[2], 240)); p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(x - w / 2 + 12, y), 4, 4)
                p.setPen(QColor(col[0], col[1], col[2], 240))
                fi = QFont("Consolas", 8); fi.setBold(True); p.setFont(fi)
                p.drawText(QRectF(x - w / 2 + 18, y - 8, 14, 16), Qt.AlignCenter, it.get("icono", ""))
                # titulo recortado
                p.setPen(QColor(220, 235, 255, 235))
                ft = QFont("Consolas", 8); p.setFont(ft)
                tt = (it.get("titulo") or "")
                if len(tt) > 26:
                    tt = tt[:25] + "…"
                p.drawText(QRectF(x - w / 2 + 26, y - 9, w - 32, 18),
                           Qt.AlignVCenter | Qt.AlignLeft, tt)

    def crear_actividad(size=420):
        return Actividad(size)
else:
    def crear_actividad(size=420):
        return {"error": "PyQt5 no disponible"}
