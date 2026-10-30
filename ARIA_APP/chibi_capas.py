# -*- coding: utf-8 -*-
"""ARIA - Motor de avatar HIBRIDO (capas + deformacion por regiones).

Idea robada de mesh-avatar-studio pero traducida a ARIA (PyQt5, local, Regla v2:
sin servidores, sin red, sin WebGL/MediaPipe pesados).

Hibrido:
  - 1 IMAGEN BASE limpia (la que genera chibi_art) -> se deforma por regiones para
    dar VIDA CONTINUA: parpadeo, respiracion, mecer el pelo y lip-sync por microfono.
    No hace falta generar 7 poses ni riggear a mano: se definen cajas aproximadas de
    ojos y boca (en config.json) y la deformacion trabaja sobre esas bandas.
  - SPRITE COMPLETO (sheet.png) solo para estados dramaticos que la deformacion no
    puede fingir (react, sleep). chibi.py cruza a esos cuando la emocion lo pide.

Este modulo NO importa PyQt: devuelve frames como numpy RGBA (H,W,4 uint8). chibi.py
los convierte a QImage. Asi es testeable sin pantalla. Solo necesita numpy (+ PIL/cv2
para cargar). sounddevice es OPCIONAL (si no esta, el lip-sync queda en 0).
"""
import os
import json
import math
import time

try:
    import numpy as np
except Exception:  # numpy es imprescindible
    np = None


# ------------------------------------------------------------------ utilidades
def _cargar_rgba(ruta):
    """Carga una imagen a numpy RGBA (H,W,4). Usa PIL; cae a cv2."""
    try:
        from PIL import Image
        with Image.open(ruta) as im:
            return np.asarray(im.convert("RGBA")).copy()
    except Exception:
        pass
    try:
        import cv2
        img = cv2.imread(ruta, cv2.IMREAD_UNCHANGED)
        if img is None:
            return None
        if img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        # BGRA -> RGBA
        return img[:, :, [2, 1, 0, 3]].copy()
    except Exception:
        return None


def _escala_vertical_banda(img, y0, y1, factor):
    """Comprime/estira verticalmente SOLO la banda [y0:y1] (factor<1 = aplasta,
    util para parpadeo; factor>1 = abre, util para boca). El resto no se mueve:
    la banda se reescala y se recentra dentro de su propio alto."""
    y0 = max(0, min(img.shape[0] - 1, int(y0)))
    y1 = max(y0 + 1, min(img.shape[0], int(y1)))
    banda = img[y0:y1]
    h = banda.shape[0]
    nh = max(1, int(round(h * factor)))
    # reescala la banda con numpy (nearest, barato)
    idx = (np.linspace(0, h - 1, nh)).astype(np.int32)
    sub = banda[idx]
    salida = img.copy()
    # centro de la banda original
    cy = (y0 + y1) // 2
    ny0 = cy - nh // 2
    ny1 = ny0 + nh
    # recorta destino a los limites de la imagen
    dy0, dy1 = max(0, ny0), min(img.shape[0], ny1)
    sy0 = dy0 - ny0
    sy1 = sy0 + (dy1 - dy0)
    # rellena la banda original con "fondo" (alpha 0) y pega la banda deformada
    salida[y0:y1] = 0
    salida[dy0:dy1] = _sobre(salida[dy0:dy1], sub[sy0:sy1])
    return salida


def _sobre(fondo, frente):
    """Alpha-composite simple frente sobre fondo (ambos RGBA mismo shape)."""
    af = frente[:, :, 3:4].astype(np.float32) / 255.0
    out = fondo.astype(np.float32)
    out[:, :, :3] = frente[:, :, :3] * af + out[:, :, :3] * (1 - af)
    out[:, :, 3:4] = np.clip(frente[:, :, 3:4].astype(np.float32) +
                             out[:, :, 3:4] * (1 - af), 0, 255)
    return out.astype(np.uint8)


def _shear_horizontal_top(img, y_hasta, px):
    """Inclina horizontalmente las filas de 0..y_hasta de forma progresiva (arriba
    se mueve mas) para 'mecer el pelo'. px = desplazamiento maximo en la fila 0."""
    if px == 0:
        return img
    out = np.zeros_like(img)
    y_hasta = max(1, min(img.shape[0], int(y_hasta)))
    for y in range(img.shape[0]):
        if y < y_hasta:
            k = (1.0 - y / y_hasta)        # 1 arriba -> 0 en y_hasta
            dx = int(round(px * k))
        else:
            dx = 0
        out[y] = np.roll(img[y], dx, axis=0)
        if dx > 0:
            out[y, :dx] = 0
        elif dx < 0:
            out[y, dx:] = 0
    return out


# ------------------------------------------------------------------ motor
class ChibiCapas:
    """Avatar hibrido: deforma 1 imagen base para dar vida continua.

    config (dict o ruta a config.json) usa fracciones 0..1 del alto/ancho:
      eye_box   = [x0,y0,x1,y1]   banda de los ojos (para parpadeo)
      mouth_box = [x0,y0,x1,y1]   banda de la boca  (para lip-sync)
    Si no vienen, usa defaults razonables para un chibi centrado.
    """
    DEF_EYE = [0.18, 0.30, 0.82, 0.44]
    DEF_MOUTH = [0.34, 0.50, 0.66, 0.60]

    def __init__(self, base_rgba, config=None, mic=False):
        self.base = base_rgba
        self.H, self.W = base_rgba.shape[:2]
        cfg = config or {}
        if isinstance(cfg, str) and os.path.isfile(cfg):
            try:
                cfg = json.load(open(cfg, encoding="utf-8"))
            except Exception:
                cfg = {}
        self.eye = cfg.get("eye_box", self.DEF_EYE)
        self.mouth = cfg.get("mouth_box", self.DEF_MOUTH)
        self._t0 = time.time()
        self._next_blink = self._t0 + 2.5
        self._blink_until = 0.0
        self._mic = None
        if mic:
            self._iniciar_mic()

    # ---- microfono (opcional, local) ----
    def _iniciar_mic(self):
        try:
            import sounddevice as sd
            self._nivel = 0.0

            def _cb(indata, frames, t, status):
                try:
                    self._nivel = float(np.sqrt(np.mean(indata ** 2)))
                except Exception:
                    self._nivel = 0.0

            self._mic = sd.InputStream(channels=1, samplerate=16000,
                                       blocksize=1024, callback=_cb)
            self._mic.start()
        except Exception:
            self._mic = None  # sin mic -> lip-sync queda en 0

    def nivel_mic(self):
        if self._mic is None:
            return 0.0
        # normaliza RMS (~0.0..0.1) a 0..1 con techo
        return max(0.0, min(1.0, getattr(self, "_nivel", 0.0) * 12.0))

    # ---- frame ----
    def frame(self, boca=None, hablando=False):
        """Devuelve un frame RGBA (numpy) con la vida continua aplicada.

        boca: 0..1 abertura manual; si None y hablando -> usa el mic."""
        t = time.time() - self._t0
        img = self.base

        # 1) respiracion: escala vertical global sutil (~2%)
        resp = 1.0 + 0.02 * math.sin(t * 1.6)
        img = _escala_vertical_banda(img, 0, self.H, resp)

        # 2) mecer el pelo: shear de la mitad superior
        sway = int(round(6 * math.sin(t * 0.9)))
        img = _shear_horizontal_top(img, self.H * 0.5, sway)

        # 3) parpadeo: aplasta la banda de ojos durante ~0.12s cada ~3-5s
        ahora = time.time()
        if ahora >= self._next_blink and self._blink_until == 0.0:
            self._blink_until = ahora + 0.12
            self._next_blink = ahora + 3.0 + (hash(int(ahora)) % 25) / 10.0
        if self._blink_until and ahora <= self._blink_until:
            ey0 = self.eye[1] * self.H
            ey1 = self.eye[3] * self.H
            img = _escala_vertical_banda(img, ey0, ey1, 0.15)  # casi cerrado
        elif self._blink_until and ahora > self._blink_until:
            self._blink_until = 0.0

        # 4) lip-sync: estira la banda de boca segun mic o 'boca'
        if boca is None:
            boca = self.nivel_mic() if hablando else 0.0
        if boca > 0.02:
            my0 = self.mouth[1] * self.H
            my1 = self.mouth[3] * self.H
            img = _escala_vertical_banda(img, my0, my1, 1.0 + 1.3 * boca)

        return img

    def cerrar(self):
        if self._mic is not None:
            try:
                self._mic.stop(); self._mic.close()
            except Exception:
                pass
            self._mic = None


# ------------------------------------------------------------------ fabrica
def desde_base(ruta_base, config=None, mic=False):
    """Crea un ChibiCapas desde la imagen base (la pose 'idle' limpia)."""
    if np is None:
        return {"error": "numpy no instalado"}
    base = _cargar_rgba(ruta_base)
    if base is None:
        return {"error": "no pude cargar %s" % ruta_base}
    return ChibiCapas(base, config, mic=mic)
