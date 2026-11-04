# -*- coding: utf-8 -*-
"""ARIA - Bandeja emergente (ventana de noticias que se desliza, estilo Linux).

Muestra lo que recolecto noticias.py en una ventana lateral que SE DESLIZA al entrar
(animacion) y que NO se sobrepone a ninguna app: va pegada al escritorio, DETRAS de
las demas ventanas (WindowStaysOnBottomHint) y sin robar el foco. Cada titular es una
tarjeta; al hacer click se abre la pagina en el navegador.

PyQt5, sin deps nuevas. Regla v2 (solo UI local). La animacion de deslizamiento usa
QPropertyAnimation (de QtCore).
"""
import os
import webbrowser

try:
    from PyQt5.QtCore import Qt, QPropertyAnimation, QPoint, QEasingCurve, QTimer
    from PyQt5.QtGui import QColor
    from PyQt5.QtWidgets import (QWidget, QApplication, QVBoxLayout, QHBoxLayout,
                                 QLabel, QScrollArea, QFrame, QPushButton)
    _QT = True
except Exception:
    _QT = False

CYAN = "#38bdf8"
VIOLETA = "#a78bfa"
TXT = "#cfe8ff"
TEAL = "#2dd4bf"
MONO = "Consolas"


if _QT:
    class _Tarjeta(QFrame):
        def __init__(self, noticia):
            super().__init__()
            self.url = noticia.get("url", "")
            self.setStyleSheet(
                "QFrame{background:rgba(10,16,34,0.7);border:1px solid rgba(56,189,248,0.3);"
                "border-radius:12px;} QFrame:hover{border:1px solid %s;}" % CYAN)
            lay = QVBoxLayout(self); lay.setContentsMargins(12, 10, 12, 10); lay.setSpacing(4)
            tit = QLabel(noticia.get("titulo", "")); tit.setWordWrap(True)
            tit.setStyleSheet("color:%s;font:600 12px '%s';" % (TXT, MONO))
            fu = QLabel("· " + noticia.get("fuente", "")); fu.setStyleSheet("color:%s;font:9px '%s';" % (TEAL, MONO))
            lay.addWidget(tit); lay.addWidget(fu)
            self.setCursor(Qt.PointingHandCursor)

        def mousePressEvent(self, e):
            if self.url:
                try:
                    webbrowser.open(self.url)
                except Exception:
                    pass

    class Bandeja(QWidget):
        def __init__(self, ancho=360):
            super().__init__(None)
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnBottomHint | Qt.Tool)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)   # no roba foco, no overlay
            self._ancho = ancho
            self._visible = False
            self._build()

        def _build(self):
            self.setStyleSheet("")
            root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
            panel = QFrame(); panel.setStyleSheet(
                "QFrame{background:rgba(6,10,22,0.92);border-left:1px solid rgba(56,189,248,0.4);}")
            pl = QVBoxLayout(panel); pl.setContentsMargins(14, 14, 14, 14); pl.setSpacing(10)
            cab = QHBoxLayout()
            t = QLabel("NOTICIAS · HOY"); t.setStyleSheet("color:%s;font:700 14px '%s';letter-spacing:2px;" % (CYAN, MONO))
            self._sub = QLabel(""); self._sub.setStyleSheet("color:%s;font:9px '%s';" % (TEAL, MONO))
            cerrar = QPushButton("×"); cerrar.setFixedSize(24, 24)
            cerrar.setStyleSheet("QPushButton{color:%s;background:transparent;border:none;font:700 16px '%s';}"
                                 "QPushButton:hover{color:%s;}" % (TXT, MONO, CYAN))
            cerrar.clicked.connect(self.ocultar)
            cab.addWidget(t); cab.addStretch(1); cab.addWidget(cerrar)
            pl.addLayout(cab); pl.addWidget(self._sub)
            self._scroll = QScrollArea(); self._scroll.setWidgetResizable(True)
            self._scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
            self._cont = QWidget(); self._cont.setStyleSheet("background:transparent;")
            self._lista = QVBoxLayout(self._cont); self._lista.setSpacing(8); self._lista.addStretch(1)
            self._scroll.setWidget(self._cont)
            pl.addWidget(self._scroll, 1)
            root.addWidget(panel)

        def showEvent(self, e):
            super().showEvent(e)
            if not getattr(self, "_blur_ok", False):
                self._blur_ok = True
                try:
                    import pywinstyles           # blur nativo de Windows (opcional, liviano)
                    pywinstyles.apply_style(self, "acrylic")
                except Exception:
                    pass

        def set_noticias(self, paquete):
            noticias = paquete.get("noticias", []) if isinstance(paquete, dict) else list(paquete)
            self._sub.setText("%d titulares · %s" % (len(noticias),
                              (paquete.get("fecha") if isinstance(paquete, dict) else "") or ""))
            # limpiar
            while self._lista.count() > 1:
                it = self._lista.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()
            for n in noticias:
                self._lista.insertWidget(self._lista.count() - 1, _Tarjeta(n))
            return len(noticias)

        def _geo(self):
            scr = QApplication.primaryScreen().availableGeometry()
            h = scr.height() - 48
            return scr, h

        def mostrar(self, paquete=None):
            if paquete is not None:
                self.set_noticias(paquete)
            scr, h = self._geo()
            self.resize(self._ancho, h)
            y = scr.top() + 24
            fuera = QPoint(scr.right(), y)                 # fuera de pantalla (derecha)
            dentro = QPoint(scr.right() - self._ancho - 8, y)
            self.move(fuera); self.show()
            self._anim = QPropertyAnimation(self, b"pos")
            self._anim.setDuration(280); self._anim.setStartValue(fuera)
            self._anim.setEndValue(dentro); self._anim.setEasingCurve(QEasingCurve.OutCubic)
            self._anim.start()
            self._visible = True

        def ocultar(self):
            scr, h = self._geo()
            y = scr.top() + 24
            self._anim = QPropertyAnimation(self, b"pos")
            self._anim.setDuration(240)
            self._anim.setStartValue(self.pos())
            self._anim.setEndValue(QPoint(scr.right(), y))
            self._anim.setEasingCurve(QEasingCurve.InCubic)
            self._anim.finished.connect(self.hide)
            self._anim.start()
            self._visible = False

        def alternar(self, paquete=None):
            self.ocultar() if self._visible else self.mostrar(paquete)

    def crear_bandeja(ancho=360):
        return Bandeja(ancho)
else:
    def crear_bandeja(ancho=360):
        return {"error": "PyQt5 no disponible"}
