# -*- coding: utf-8 -*-
"""ARIA - Bandeja del sistema (modo silencioso).

ARIA puede vivir en la bandeja de Windows sin ventana visible: nadie la ve
trabajando y no estorba. Solo PyQt5 + stdlib (Regla v2): sin HTTP, sin
servidores, sin dependencias nuevas.

Uso (desde run_desktop):
    from bandeja_sistema import BandejaARIA
    bandeja = BandejaARIA(window, app)
    if bandeja.disponible():
        bandeja.arrancar()
"""
from __future__ import annotations

from PyQt5.QtCore import QObject, Qt
from PyQt5.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap, QRadialGradient
from PyQt5.QtWidgets import QApplication, QMenu, QSystemTrayIcon


def icono_aria(tam: int = 64) -> QIcon:
    """Orbe cyan dibujado en memoria: cero archivos externos."""
    pm = QPixmap(tam, tam)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QRadialGradient(tam * 0.5, tam * 0.5, tam * 0.48)
    g.setColorAt(0.0, QColor(125, 211, 252, 255))
    g.setColorAt(0.5, QColor(56, 189, 248, 210))
    g.setColorAt(1.0, QColor(15, 23, 42, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(2, 2, tam - 4, tam - 4)
    p.setBrush(QColor(226, 232, 240))
    p.drawEllipse(int(tam * 0.37), int(tam * 0.37), int(tam * 0.26), int(tam * 0.26))
    p.end()
    return QIcon(pm)


class BandejaARIA(QObject):
    """Icono en la bandeja + menu Mostrar / Ocultar / Salir.

    Regla dura: cerrar la ventana NO cierra ARIA. Solo `salir()` termina el
    proceso, y lo hace marcando la ventana con `_salir_real = True` para que
    su closeEvent acepte el cierre en vez de esconderse.
    """

    def __init__(self, ventana, app=None, parent=None):
        super().__init__(parent if parent is not None else ventana)
        self.ventana = ventana
        self.app = app if app is not None else QApplication.instance()
        self.salio = False

        self.tray = QSystemTrayIcon(icono_aria(), self)
        self.tray.setToolTip("ARIA - en linea (segundo plano)")

        self.menu = QMenu()
        self.act_mostrar = self.menu.addAction("Mostrar")
        self.act_ocultar = self.menu.addAction("Ocultar")
        self.menu.addSeparator()
        self.act_salir = self.menu.addAction("Salir")
        self.act_mostrar.triggered.connect(self.mostrar)
        self.act_ocultar.triggered.connect(self.ocultar)
        self.act_salir.triggered.connect(self.salir)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._al_activar)
        self._sincronizar()

    # ---- estado ----
    def activa(self) -> bool:
        try:
            return self.tray.isVisible()
        except Exception:
            return False

    def _sincronizar(self):
        visible = False
        try:
            visible = bool(self.ventana.isVisible())
        except Exception:
            pass
        self.act_mostrar.setEnabled(True)
        self.act_ocultar.setEnabled(visible)
        self.tray.setToolTip("ARIA - %s" % ("ventana visible" if visible else "en segundo plano"))

    # ---- ciclo de vida ----
    def disponible(self) -> bool:
        try:
            return QSystemTrayIcon.isSystemTrayAvailable()
        except Exception:
            return False

    def arrancar(self) -> bool:
        if not self.disponible():
            return False
        if self.app is not None:
            self.app.setQuitOnLastWindowClosed(False)
        self.tray.show()
        self._sincronizar()
        return self.activa()

    # ---- acciones ----
    def mostrar(self):
        try:
            self.ventana.show()
            self.ventana.raise_()
            self.ventana.activateWindow()
        except Exception:
            pass
        self._sincronizar()

    def ocultar(self):
        try:
            self.ventana.hide()
        except Exception:
            pass
        self._sincronizar()

    def salir(self):
        self.salio = True
        try:
            self.ventana._salir_real = True
        except Exception:
            pass
        try:
            self.tray.hide()
            self.tray.setVisible(False)
        except Exception:
            pass
        try:
            if self.app is not None:
                self.app.quit()
        except Exception:
            pass

    def _al_activar(self, motivo):
        # doble clic (y clic simple en Windows) devuelve la ventana
        if motivo in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.mostrar()
