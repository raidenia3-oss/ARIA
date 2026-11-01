# -*- coding: utf-8 -*-
"""ARIA - Deteccion de presencia (estas usando la PC, o no?).

Mide la INACTIVIDAD global del sistema (teclado + mouse en TODO Windows, no solo
sobre la ventana de ARIA) con GetLastInputInfo. Si hay actividad -> estas 'activo' y
ARIA aparece; si llevas un rato sin tocar nada -> 'ausente' y ARIA se esconde en
segundo plano.

Regla v2: local, sin red, sin servidores. Usa ctypes (stdlib) contra la API de Windows.
La clasificacion/transicion es PURA (sin ctypes ni Qt): testeable.
"""
import time


def inactividad_segundos():
    """Segundos desde la ultima actividad de teclado/mouse en el sistema (Windows).
    Si no se puede medir (otro SO o error), devuelve 0.0 (asume activo)."""
    try:
        import ctypes

        class _LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        lii = _LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            ahora = ctypes.windll.kernel32.GetTickCount()
            return max(0.0, (ahora - lii.dwTime) / 1000.0)
    except Exception:
        pass
    return 0.0


def _clasificar(inactividad, umbral_ausente=120):
    """inactividad (seg) -> 'activo' | 'ausente'."""
    return "ausente" if inactividad >= umbral_ausente else "activo"


def estado(umbral_ausente=120):
    """Estado de presencia actual."""
    return _clasificar(inactividad_segundos(), umbral_ausente)


def _transicion(estado_actual, inactividad, umbral_ausente=120, margen=10):
    """Maquina de estados con histeresis para no parpadear:
      - pasa a 'ausente' cuando la inactividad supera el umbral
      - vuelve a 'activo' apenas hay actividad reciente (inactividad < margen)
    Devuelve el nuevo estado. Pura, testeable."""
    if estado_actual == "activo":
        return "ausente" if inactividad >= umbral_ausente else "activo"
    # estaba ausente: vuelve a activo solo con actividad clara y reciente
    return "activo" if inactividad < margen else "ausente"


class Vigia:
    """Observa la presencia y avisa en las TRANSICIONES (no cada tick).

    on_activo()  -> llamalo para MOSTRAR ARIA (apareces)
    on_ausente() -> llamalo para ESCONDER ARIA en segundo plano (te vas)

    Si PyQt5 esta, usa un QTimer; si no, expone paso() para que lo llames tu."""
    def __init__(self, on_activo=None, on_ausente=None, umbral_ausente=120, intervalo_ms=1000):
        self.on_activo = on_activo
        self.on_ausente = on_ausente
        self.umbral = umbral_ausente
        self.intervalo_ms = intervalo_ms
        self._estado = "activo"
        self._timer = None

    def paso(self):
        """Un ciclo: lee inactividad, decide, y dispara callback si hubo transicion."""
        nuevo = _transicion(self._estado, inactividad_segundos(), self.umbral)
        if nuevo != self._estado:
            self._estado = nuevo
            cb = self.on_activo if nuevo == "activo" else self.on_ausente
            if callable(cb):
                try:
                    cb()
                except Exception:
                    pass
        return self._estado

    def iniciar(self):
        """Arranca el muestreo. Con Qt usa QTimer; devuelve True si quedo corriendo."""
        try:
            from PyQt5.QtCore import QTimer
            self._timer = QTimer()
            self._timer.timeout.connect(self.paso)
            self._timer.start(self.intervalo_ms)
            return True
        except Exception:
            return False

    def detener(self):
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None


def crear_vigia(on_activo=None, on_ausente=None, umbral_ausente=120):
    return Vigia(on_activo, on_ausente, umbral_ausente)
