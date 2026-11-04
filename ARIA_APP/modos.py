# -*- coding: utf-8 -*-
"""ARIA - Nucleo de Modos + Evolucion (idea robada de dos MECANICAS, no de personajes).

De TENSURA tomamos la ESTRUCTURA del 'Gran Sabio': una mente analitica que ANALIZA,
PREDICE y sobre todo EVOLUCIONA acumulando lo que aprende hasta ascender de forma.
De BEN 10 tomamos la del OMNITRIX: un selector que CAMBIA de FORMA/modo, y cada forma
desbloquea un set distinto de habilidades.

NO copiamos nada con dueno (ni Rafael/Gran Sabio, ni el reloj verde del Omnitrix, ni sus
disenos): son franquicias protegidas. Robamos SOLO la idea mecanica y la volvemos algo
propio de ARIA, con nombres y estetica originales (cyan/violeta, su nucleo).

Lo bonito: ARIA YA es un 'Gran Sabio' por dentro. Este modulo le pone cara a eso:
  - El SELECTOR (dial tipo Omnitrix, original) cambia su MODO de operacion. Cada modo
    es un bundle de skills que ya tiene (analista, vigia, social, creadora, ...).
  - El medidor de EVOLUCION (tipo Gran Sabio) NO es decorativo: se calcula de datos
    REALES de ARIA (nodos de conocimiento, conceptos dominados, lecciones, auto-mejoras).

Toda la LOGICA (registro de modos, ciclado, calculo de evolucion) es PURA y testeable.
La parte visual (Selector) usa solo QPainter + 1 QPropertyAnimation. Regla v2: UI local,
sin servidores. pywinstyles (blur nativo) es opcional.
"""

# ======================================================================= LOGICA PURA

# Modos de operacion de ARIA. Cada modo = una FORMA (Omnitrix) con su set de skills
# (que ARIA ya tiene) + un color + un lema. Nombres ORIGINALES (nada con dueno).
# 'req' = etapa de EVOLUCION minima para DESBLOQUEAR el modo (idea Gran Sabio: ganas
# formas al evolucionar). ARIA nace solo con ANALISTA y libera el resto al crecer.
# El mas peligroso (ARQUITECTA: se reescribe sola) se desbloquea de ultimo.
MODOS = [
    {"id": "analista",  "nombre": "ANALISTA",  "color": "#38bdf8", "lema": "Analiza y predice.",
     "skills": ["conocimiento", "investigacion", "certeza", "coherencia", "atomizacion"],
     "forma": "nucleo", "req": 0},
    {"id": "vigia",     "nombre": "VIGIA",     "color": "#2dd4bf", "lema": "Explora el mundo de hoy.",
     "skills": ["noticias", "bandeja", "brief"],
     "forma": "nucleo", "req": 1},
    {"id": "social",    "nombre": "SOCIAL",    "color": "#a78bfa", "lema": "Lee a la gente.",
     "skills": ["social_skills", "conversacion", "social_rolemodels"],
     "forma": "avatar", "req": 2},
    {"id": "creadora",  "nombre": "CREADORA",  "color": "#f0abfc", "lema": "Crea imagen y forma.",
     "skills": ["gen_local", "chibi_art"],
     "forma": "avatar", "req": 4},
    {"id": "mentora",   "nombre": "MENTORA",   "color": "#fbbf24", "lema": "Te ensena de verdad.",
     "skills": ["aprendizaje", "planificador"],
     "forma": "avatar", "req": 3},
    {"id": "arquitecta", "nombre": "ARQUITECTA", "color": "#f87171", "lema": "Se mejora a si misma.",
     "skills": ["mejora", "autodiagnostico", "auditoria", "autonomia_guardia"],
     "forma": "nucleo", "req": 5},
]

# Etapas de EVOLUCION (idea Gran Sabio), con nombres originales. Cada una pide un
# 'puntaje' minimo. El puntaje sale de datos reales (ver puntaje_evolucion()).
ETAPAS = [
    (0,    "SEMILLA",       "Apenas despierta."),
    (20,   "DESPIERTA",     "Ya conecta ideas."),
    (60,   "ANALITICA",     "Ve patrones."),
    (140,  "SABIA",         "Predice y aconseja."),
    (300,  "EVOLUCIONADA",  "Se corrige sola."),
    (600,  "NUCLEO PLENO",  "Mente integrada."),
]


def siguiente(idx, n=None):
    """Indice del modo siguiente (cicla). Puro."""
    n = n if n is not None else len(MODOS)
    return (idx + 1) % n if n else 0


def anterior(idx, n=None):
    n = n if n is not None else len(MODOS)
    return (idx - 1) % n if n else 0


def por_id(mid):
    """Devuelve (idx, modo) por id, o (0, primer modo) si no existe."""
    for i, m in enumerate(MODOS):
        if m["id"] == mid:
            return i, m
    return 0, MODOS[0]


def desbloqueado(modo, evo_idx):
    """True si la etapa de evolucion actual (evo_idx) alcanza el 'req' del modo. Puro."""
    return int(evo_idx) >= int(modo.get("req", 0))


def modos_desbloqueados(evo_idx):
    """Lista de ids de modos ya disponibles en esta etapa. Puro."""
    return [m["id"] for m in MODOS if desbloqueado(m, evo_idx)]


def puntaje_evolucion(stats):
    """Convierte estadisticas REALES de ARIA en un puntaje de evolucion. Puro.

    stats = {nodos, aristas, dominados, lecciones, mejoras, conceptos}
    Pesos: lo que cuesta mas (dominar, mejorarse) pesa mas que solo acumular.
    """
    s = stats or {}
    return int(
        1.0 * s.get("nodos", 0) +
        0.5 * s.get("aristas", 0) +
        4.0 * s.get("dominados", 0) +
        2.0 * s.get("lecciones", 0) +
        8.0 * s.get("mejoras", 0) +
        0.5 * s.get("conceptos", 0)
    )


def etapa(puntaje):
    """Dada la puntuacion, devuelve dict con etapa actual, progreso a la siguiente, etc.
    Puro y testeable."""
    idx = 0
    for i, (minimo, _n, _d) in enumerate(ETAPAS):
        if puntaje >= minimo:
            idx = i
    minimo, nombre, desc = ETAPAS[idx]
    if idx + 1 < len(ETAPAS):
        sig_min = ETAPAS[idx + 1][0]
        span = max(1, sig_min - minimo)
        progreso = max(0.0, min(1.0, (puntaje - minimo) / float(span)))
        falta = max(0, sig_min - puntaje)
        sig_nombre = ETAPAS[idx + 1][1]
    else:
        progreso, falta, sig_nombre = 1.0, 0, None
    return {"idx": idx, "nombre": nombre, "desc": desc, "puntaje": puntaje,
            "progreso": round(progreso, 3), "falta": falta, "siguiente": sig_nombre,
            "max": idx + 1 >= len(ETAPAS)}


def recoger_stats():
    """Lee datos REALES de los subsistemas de ARIA (todos opcionales/guardados).
    Impuro (toca modulos) pero nunca lanza: si algo falta, cuenta 0."""
    st = {"nodos": 0, "aristas": 0, "dominados": 0, "lecciones": 0,
          "mejoras": 0, "conceptos": 0}
    # conocimiento (grafo)
    try:
        import conocimiento
        g = conocimiento.grafo()
        db = g._conn() if hasattr(g, "_conn") else None
        if db is not None:
            st["nodos"] = db.execute("SELECT COUNT(*) FROM nodos").fetchone()[0]
            st["aristas"] = db.execute("SELECT COUNT(*) FROM aristas").fetchone()[0]
    except Exception:
        pass
    # aprendizaje (dominio)
    try:
        import aprendizaje
        res = aprendizaje.arnes().resumen()
        st["conceptos"] = res.get("conceptos", 0)
        st["dominados"] = res.get("dominados", 0)
    except Exception:
        pass
    # experiencia (lecciones)
    try:
        import experiencia
        ex = experiencia.Experiencia() if hasattr(experiencia, "Experiencia") else None
        if ex is not None and hasattr(ex, "resumen"):
            r = ex.resumen()
            st["lecciones"] = (r.get("lecciones") if isinstance(r, dict) else 0) or 0
    except Exception:
        pass
    # mejora (auto-mejoras aprobadas)
    try:
        import mejora as _m
        if hasattr(_m, "historial"):
            st["mejoras"] = len([x for x in _m.historial() if x.get("estado") == "aprobada"])
    except Exception:
        pass
    return st


def evolucion_actual():
    """Atajo: stats reales -> etapa. Usalo para mostrar en la UI."""
    return etapa(puntaje_evolucion(recoger_stats()))


# ====================================================================== PARTE VISUAL
import math

try:
    from PyQt5.QtCore import (Qt, QTimer, QPoint, QPointF, QRectF, QPropertyAnimation,
                              QEasingCurve, pyqtProperty)
    from PyQt5.QtGui import QPainter, QColor, QPen, QRadialGradient, QFont
    from PyQt5.QtWidgets import QWidget, QApplication
    _QT = True
except Exception:
    _QT = False


def _rgb(hexc):
    h = hexc.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


if _QT:
    class Selector(QWidget):
        """Dial circular (estilo Omnitrix, original) para cambiar el MODO de ARIA, con
        anillo de EVOLUCION (estilo Gran Sabio) alimentado por datos reales.

        - Rueda del mouse: gira el dial (modo anterior/siguiente).
        - Click en un punto de modo: salta a ese modo.
        - Arrastrar desde el centro: mueve la ventana.
        on_modo(modo_dict) se llama al cambiar de modo (para que el runtime active skills).
        """
        def __init__(self, size=300, on_modo=None, modo_inicial="analista", nucleo=None):
            super().__init__(None)
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnBottomHint | Qt.Tool)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)   # no roba foco, no overlay
            self.resize(size, size)
            self._s = size
            self._on_modo = on_modo
            self._nucleo = nucleo                  # orbe a retenir al cambiar de modo (c)
            self._flash = 0.0                      # destello rojo al tocar un modo bloqueado
            self._idx, _ = por_id(modo_inicial)
            self._n = len(MODOS)
            self._rot_val = self._rot_objetivo()      # grados de rotacion del anillo
            self._t = 0.0
            self._drag = None
            self._evo = etapa(0)                       # se refresca al mostrar / por timer
            self._anim = None
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)

        # -- animacion de giro del dial (propiedad Qt) --
        def _get_rot(self):
            return self._rot_val

        def _set_rot(self, v):
            self._rot_val = v
            self.update()
        rot = pyqtProperty(float, fget=_get_rot, fset=_set_rot)

        def _rot_objetivo(self, idx=None):
            """Rotacion que lleva el modo activo arriba (12 en punto)."""
            idx = self._idx if idx is None else idx
            return -(idx * (360.0 / max(1, len(MODOS))))

        # -- ciclo de vida --
        def start(self, fps=20):
            self.refrescar_evolucion()
            # tinte inicial del orbe segun el modo de arranque
            if self._nucleo is not None and hasattr(self._nucleo, "set_tint"):
                try:
                    self._nucleo.set_tint(MODOS[self._idx]["color"])
                except Exception:
                    pass
            self._timer.start(int(1000 / fps))
            scr = QApplication.primaryScreen().availableGeometry() if QApplication.instance() else None
            if scr:
                self.move(scr.center().x() - self._s // 2, scr.center().y() - self._s // 2)
            self.show()

        def _tick(self):
            self._t += 0.05
            if self._flash > 0:
                self._flash = max(0.0, self._flash - 0.05)
            self.update()

        # -- panel deslizable del shell (a): entra/sale desde el borde derecho --
        def deslizar_entrada(self, margen=16):
            scr = QApplication.primaryScreen().availableGeometry()
            y = scr.center().y() - self._s // 2
            fuera = QPoint(scr.right(), y)
            dentro = QPoint(scr.right() - self._s - margen, y)
            self.move(fuera); self.show()
            self._slide = QPropertyAnimation(self, b"pos")
            self._slide.setDuration(300); self._slide.setStartValue(fuera)
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

        def showEvent(self, e):
            super().showEvent(e)
            if not getattr(self, "_blur_ok", False):
                self._blur_ok = True
                try:
                    import pywinstyles           # blur nativo de Windows (opcional, liviano)
                    pywinstyles.apply_style(self, "acrylic")
                except Exception:
                    pass

        def refrescar_evolucion(self):
            """Relee datos reales de ARIA y actualiza la etapa mostrada."""
            try:
                self._evo = evolucion_actual()
            except Exception:
                self._evo = etapa(0)
            self.update()
            return self._evo

        # -- seleccion --
        def seleccionar(self, idx, animar=True):
            idx = idx % self._n
            if idx == self._idx:
                return
            # gating por evolucion (b): si el modo no esta desbloqueado, destella y no cambia
            if not desbloqueado(MODOS[idx], self._evo.get("idx", 0)):
                self._flash = 1.0
                return
            self._idx = idx
            destino = self._rot_objetivo(idx)
            # tomar el camino corto (no girar 300 grados por dar la vuelta)
            actual = self._rot_val
            while destino - actual > 180:
                destino -= 360
            while destino - actual < -180:
                destino += 360
            if animar:
                self._anim = QPropertyAnimation(self, b"rot")
                self._anim.setDuration(380)
                self._anim.setStartValue(actual)
                self._anim.setEndValue(destino)
                self._anim.setEasingCurve(QEasingCurve.OutBack)
                self._anim.start()
            else:
                self._set_rot(destino)
            m = MODOS[self._idx]
            # (c) retenir el orbe hacia el color del modo activo
            if self._nucleo is not None and hasattr(self._nucleo, "set_tint"):
                try:
                    self._nucleo.set_tint(m["color"])
                except Exception:
                    pass
            if callable(self._on_modo):
                try:
                    self._on_modo(dict(m))
                except Exception:
                    pass

        def modo_actual(self):
            return dict(MODOS[self._idx])

        # -- interaccion --
        def wheelEvent(self, e):
            paso = 1 if e.angleDelta().y() < 0 else -1
            self.seleccionar((self._idx + paso) % self._n)

        def mousePressEvent(self, e):
            if e.button() != Qt.LeftButton:
                return
            c = self._s / 2.0
            dx, dy = e.pos().x() - c, e.pos().y() - c
            dist = math.hypot(dx, dy)
            if dist < self._s * 0.22:          # centro -> arrastrar ventana
                self._drag = e.globalPos() - self.pos()
                return
            if dist > self._s * 0.30:          # anillo de modos -> elegir el mas cercano
                ang = (math.degrees(math.atan2(dy, dx)) - self._rot_val + 90) % 360
                idx = int(round(ang / (360.0 / self._n))) % self._n
                self.seleccionar(idx)

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
            m = MODOS[self._idx]
            col = _rgb(m["color"])
            self._base(p, S, c, col)
            self._anillo_evolucion(p, S, c)
            self._anillo_modos(p, S, c, col)
            self._centro(p, S, c, col, m)
            p.end()

        def _base(self, p, S, c, col):
            g = QRadialGradient(c, c, c)
            g.setColorAt(0, QColor(12, 18, 34, 220))
            g.setColorAt(1, QColor(4, 8, 18, 140))
            p.setBrush(g); p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(0, 0, S, S))

        def _anillo_evolucion(self, p, S, c):
            """Anillo exterior: progreso dentro de la etapa de evolucion actual."""
            r = S * 0.46
            rect = QRectF(c - r, c - r, 2 * r, 2 * r)
            p.setBrush(Qt.NoBrush)
            # pista tenue
            p.setPen(QPen(QColor(120, 160, 200, 45), 2.0))
            p.drawEllipse(rect)
            # progreso (desde arriba, horario)
            prog = self._evo.get("progreso", 0.0)
            p.setPen(QPen(QColor(56, 189, 248, 210), 3.0, cap=Qt.RoundCap))
            p.drawArc(rect, 90 * 16, -int(360 * prog * 16))

        def _anillo_modos(self, p, S, c, col):
            """Puntos de los modos alrededor; el activo, grande y brillante; los
            BLOQUEADOS (evolucion insuficiente) atenuados con un candado."""
            evo_idx = self._evo.get("idx", 0)
            r = S * 0.37
            paso = 360.0 / self._n
            for i, mm in enumerate(MODOS):
                ang = math.radians(self._rot_val - 90 + i * paso)
                x = c + r * math.cos(ang)
                y = c + r * math.sin(ang)
                mc = _rgb(mm["color"])
                bloq = not desbloqueado(mm, evo_idx)
                activo = (i == self._idx)
                if bloq:
                    # punto apagado + aro de candado
                    p.setBrush(QColor(120, 140, 160, 55)); p.setPen(Qt.NoPen)
                    p.drawEllipse(QPointF(x, y), 3.0, 3.0)
                    p.setBrush(Qt.NoBrush)
                    p.setPen(QPen(QColor(150, 170, 190, 90), 1.2))
                    p.drawArc(QRectF(x - 5, y - 4, 10, 9), 0, 180 * 16)
                    continue
                rad = 7 if activo else 3.5
                a = 255 if activo else 120
                if activo:
                    gl = QRadialGradient(x, y, 16)
                    gl.setColorAt(0, QColor(mc[0], mc[1], mc[2], 150))
                    gl.setColorAt(1, QColor(mc[0], mc[1], mc[2], 0))
                    p.setBrush(gl); p.setPen(Qt.NoPen)
                    p.drawEllipse(QPointF(x, y), 16, 16)
                p.setBrush(QColor(mc[0], mc[1], mc[2], a)); p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(x, y), rad, rad)
            # destello rojo al tocar un modo bloqueado
            if self._flash > 0:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(248, 113, 113, int(200 * self._flash)), 2.5))
                rr = S * 0.46
                p.drawEllipse(QRectF(c - rr, c - rr, 2 * rr, 2 * rr))

        def _centro(self, p, S, c, col, m):
            # orbe central con el color del modo activo (late suave)
            pulso = 1.0 + 0.04 * math.sin(self._t * 2.0)
            r = S * 0.20 * pulso
            g = QRadialGradient(c, c, r)
            g.setColorAt(0, QColor(col[0], col[1], col[2], 230))
            g.setColorAt(0.7, QColor(col[0], col[1], col[2], 90))
            g.setColorAt(1, QColor(col[0], col[1], col[2], 0))
            p.setBrush(g); p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(c, c), r, r)
            # textos: etapa (arriba), nombre del modo (centro), lema (abajo)
            p.setPen(QColor(205, 232, 255, 230))
            fe = QFont("Consolas", 8); fe.setLetterSpacing(QFont.AbsoluteSpacing, 1.5)
            p.setFont(fe)
            p.drawText(QRectF(0, c - S * 0.17, S, 16), Qt.AlignCenter,
                       "LVL %d  %s" % (self._evo.get("idx", 0), self._evo.get("nombre", "")))
            fn = QFont("Consolas", 15); fn.setBold(True)
            p.setFont(fn); p.setPen(QColor(255, 255, 255, 240))
            p.drawText(QRectF(0, c - 14, S, 28), Qt.AlignCenter, m["nombre"])
            fl = QFont("Consolas", 8)
            p.setFont(fl); p.setPen(QColor(col[0], col[1], col[2], 220))
            p.drawText(QRectF(0, c + S * 0.12, S, 16), Qt.AlignCenter, m["lema"])

    def crear_selector(size=300, on_modo=None, modo_inicial="analista", nucleo=None):
        return Selector(size=size, on_modo=on_modo, modo_inicial=modo_inicial, nucleo=nucleo)
else:
    def crear_selector(size=300, on_modo=None, modo_inicial="analista", nucleo=None):
        return {"error": "PyQt5 no disponible"}
