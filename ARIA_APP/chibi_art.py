# -*- coding: utf-8 -*-
"""ARIA - Pipeline para que ARIA cree su propio sprite-sheet chibi.

Flujo (en la PC de Raiden, con internet):
  1) genera cada pose con gen_imagen (texto->imagen, fondo blanco)
  2) recorta el watermark inferior y le quita el fondo -> transparente (rembg)
  3) arma el sheet.png (1 columna x N poses) + config.json (con cajas ojos/boca)
El motor chibi.py consume ese sheet+config; chibi_capas.py usa la pose 'idle' como
imagen base para la animacion hibrida (parpadeo/respiracion/lip-sync).

Diseno ORIGINAL (fusion de rasgos, no copia de personajes con copyright).
Fusion: pelo blanco (Echidna) + vestido gotico de bruja negro/blanco (Echidna) +
cuerpo/proporcion chibi petite (Iroha) + audifonos rosa/blanco (Iroha) + ojos cyan leales.
"""
import os
import json
import time

_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMA_DIR = lambda tema: os.path.join(_DIR, "assets", "chibi", tema)

PROMPT_BASE = ("chibi anime mascot, original character, small compact chibi body with Iroha-like "
               "petite proportions (2-head-tall), very long flowing straight pure white hair past "
               "the waist (Echidna style), black-and-white gothic witch dress with white lace frills "
               "and layered skirt (Echidna style), soft pink and white over-ear headphones resting "
               "around the neck, large expressive cyan eyes with a calm devoted loyal gaze, pale skin, "
               "small green butterfly hair clip, soft blush, clean cel-shaded anime style, centered, "
               "full body, plain solid white background, no watermark, no text, no logo")

# expresiones: rango picaro/travieso (Iroha) + calma leal (Ciel)
POSES = [
    ("idle",   "standing elegant, calm loyal gentle smile"),
    ("walk",   "walking gracefully to the side, mid-step, confident"),
    ("talk",   "cheeky playful teasing smile, talking, one hand raised"),
    ("think",  "thoughtful, finger on chin, looking up, curious"),
    ("listen", "attentive and devoted, hand touching the headphones, listening"),
    ("sleep",  "eyes closed, peaceful sleeping, slight smile"),
    ("react",  "surprised and flustered, wide cyan eyes, big blush, hands up"),
]

# cajas aproximadas (fracciones 0..1) para la deformacion hibrida de chibi_capas
EYE_BOX = [0.18, 0.30, 0.82, 0.44]
MOUTH_BOX = [0.34, 0.50, 0.66, 0.60]


def disponible():
    try:
        import cv2  # noqa
        import numpy  # noqa
        import gen_imagen  # noqa
        return True
    except Exception:
        return False


def _recortar_marca(im, frac=0.14):
    """Recorta la franja inferior donde cae el watermark (pollinations.ai va abajo
    al centro). Devuelve la imagen PIL sin esa franja."""
    w, h = im.size
    corte = int(h * (1.0 - frac))
    return im.crop((0, 0, w, corte))


def quitar_fondo(ruta_in, ruta_out):
    """Quita el fondo -> transparente con rembg (segmentacion real, cualquier color
    de fondo). ANTES recorta la franja inferior del watermark. rembg es OBLIGATORIO:
    el recorte por blanco no sirve con fondos oscuros/teal (deja el fondo opaco), asi
    que si rembg no esta, devuelve error claro para que se instale."""
    try:
        from rembg import remove
        from PIL import Image
    except Exception:
        return {"error": "rembg no instalado (pip install rembg onnxruntime) - "
                         "obligatorio para recorte limpio en las 7 poses"}
    try:
        with Image.open(ruta_in) as im:
            im = _recortar_marca(im.convert("RGBA"))   # fuera el watermark
            out = remove(im)                            # segmenta al personaje
        out.save(ruta_out)
        return {"ok": True, "ruta": ruta_out}
    except Exception as exc:
        return {"error": "rembg fallo: %s" % exc}


def generar_sheet(tema="cyberpunk", size=256, estilo_extra="", pausa=16):
    """Genera las poses, quita fondo y arma sheet.png + config.json. Requiere internet.

    'pausa' = segundos entre poses (el tier gratis limita ~1 imagen/15s)."""
    if not disponible():
        return {"error": "faltan cv2/numpy/gen_imagen"}
    import cv2
    import numpy as np
    import gen_imagen

    destino = _TEMA_DIR(tema)
    tmp = os.path.join(destino, "_tmp")
    os.makedirs(tmp, exist_ok=True)

    filas = []
    for i, (estado, pose) in enumerate(POSES):
        prompt = PROMPT_BASE + ", " + pose + ((", " + estilo_extra) if estilo_extra else "")
        jpg = os.path.join(tmp, "%s.jpg" % estado)
        r = gen_imagen.generar(prompt, w=size, h=size, archivo=jpg, seed=1000 + i)
        if not r.get("ok"):
            return {"error": "pose '%s': %s" % (estado, r.get("error"))}
        png = os.path.join(tmp, "%s.png" % estado)
        qf = quitar_fondo(jpg, png)
        if not qf.get("ok"):
            return {"error": "pose '%s': %s" % (estado, qf.get("error"))}
        cell = cv2.imread(png, cv2.IMREAD_UNCHANGED)
        if cell is None:
            return {"error": "no pude leer '%s'" % estado}
        if cell.shape[0] != size or cell.shape[1] != size:
            cell = cv2.resize(cell, (size, size))
        filas.append((estado, cell))
        if i < len(POSES) - 1 and pausa:
            time.sleep(pausa)   # respetar el limite del tier gratis

    # armar sheet vertical: 1 columna x N filas
    canvas = np.zeros((size * len(filas), size, 4), dtype=np.uint8)
    states_cfg = {}
    for i, (estado, cell) in enumerate(filas):
        canvas[i * size:(i + 1) * size, 0:size] = cell
        states_cfg[estado] = {"fila": i, "frames": 1, "fps": 6}

    os.makedirs(destino, exist_ok=True)
    sheet = os.path.join(destino, "sheet.png")
    cv2.imwrite(sheet, canvas)
    cfg = {"frame_w": size, "frame_h": size, "states": states_cfg,
           "eye_box": EYE_BOX, "mouth_box": MOUTH_BOX,
           "base_state": "idle"}   # pose base para chibi_capas (animacion hibrida)
    with open(os.path.join(destino, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    return {"ok": True, "sheet": sheet, "config": os.path.join(destino, "config.json"),
            "resumen": "Avatar chibi generado: %d poses en %s" % (len(filas), sheet)}
