"""AURA MorphWallpaperEngine — Motor de IA gráfica para procesamiento de wallpapers.

Funciones:
  - upscale_image(): Nítidez y resolución con OpenCV
  - remove_obstacles(): Inpainting para eliminar elementos no deseados
  - generate_depth_layers(): Segmentación sujeto/fondo para efecto profundidad
"""

import io, logging, tempfile, time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("aura.morph_engine")

MORPH_OUTPUT = Path(__file__).resolve().parent.parent / "web_vault" / "morph_output"
MORPH_OUTPUT.mkdir(parents=True, exist_ok=True)


async def upscale_image(img_bytes: bytes, scale: float = 2.0) -> bytes:
    """Corrige imágenes borrosas: nítidez + superresolución por escala.
    Devuelve bytes PNG procesados."""
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("No se pudo decodificar la imagen")
    h, w = img.shape[:2]
    new_w, new_h = int(w * scale), int(h * scale)
    upscaled = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    lab = cv2.cvtColor(upscaled, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    enhanced = cv2.merge([l, a, b])
    enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    kernel = np.array([[-0.5, -0.5, -0.5], [-0.5, 5.0, -0.5], [-0.5, -0.5, -0.5]])
    sharpened = cv2.filter2D(enhanced, -1, kernel)
    _, buf = cv2.imencode(".png", sharpened)
    log.info(f"Upscaled: {w}x{h} -> {new_w}x{new_h}")
    return buf.tobytes()


async def remove_obstacles(img_bytes: bytes, mask_region: Optional[tuple] = None) -> bytes:
    """Inpainting básico para rellenar elementos no deseados.
    mask_region: (x, y, w, h) de la zona a eliminar. Si None, detecta bordes."""
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("No se pudo decodificar la imagen")
    h, w = img.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    if mask_region:
        x, y, rw, rh = mask_region
        mask[y : y + rh, x : x + rw] = 255
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        mask = cv2.dilate(edges, kernel, iterations=3)
        border = 20
        mask[:border, :] = 0
        mask[-border:, :] = 0
        mask[:, :border] = 0
        mask[:, -border:] = 0
    result = cv2.inpaint(img, mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
    _, buf = cv2.imencode(".png", result)
    log.info("Obstacles removed via inpainting")
    return buf.tobytes()


async def generate_depth_layers(img_bytes: bytes) -> dict:
    """Segmenta sujeto principal del fondo.
    Devuelve dict con 'subject' (PNG transparente) y 'background' (fondo limpio)."""
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("No se pudo decodificar la imagen")
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    h, w = img.shape[:2]
    if img.shape[2] == 4:
        img_bgr = img[:, :, :3]
    else:
        img_bgr = img
    bg_subtractor = cv2.createBackgroundSubtractorMOG2(
        history=500, varThreshold=40, detectShadows=False
    )
    single_frame = cv2.resize(img_bgr, (640, 480))
    fg_mask = bg_subtractor.apply(single_frame)
    resized_mask = cv2.resize(fg_mask, (w, h), interpolation=cv2.INTER_LINEAR)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    cleaned_mask = cv2.morphologyEx(resized_mask, cv2.MORPH_CLOSE, kernel)
    cleaned_mask = cv2.morphologyEx(cleaned_mask, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) > (h * w * 0.01):
            hull_mask = np.zeros_like(cleaned_mask)
            hull = cv2.convexHull(largest)
            cv2.fillConvexPoly(hull_mask, hull, 255)
            blur = cv2.GaussianBlur(hull_mask, (21, 21), 0)
            cleaned_mask = blur
    subject_rgba = np.zeros((h, w, 4), dtype=np.uint8)
    subject_rgba[:, :, :3] = img_bgr
    subject_rgba[:, :, 3] = cleaned_mask
    subject_buf = cv2.imencode(".png", subject_rgba)[0]
    inv_mask = cv2.bitwise_not(cleaned_mask)
    bg_clean = img_bgr.copy()
    bg_fill = cv2.GaussianBlur(img_bgr, (51, 51), 0)
    bg_clean[inv_mask < 128] = bg_fill[inv_mask < 128]
    bg_buf = cv2.imencode(".png", bg_clean)[0]
    out_dir = MORPH_OUTPUT / f"depth_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "subject.png").write_bytes(subject_buf.tobytes())
    (out_dir / "background.png").write_bytes(bg_buf.tobytes())
    log.info(f"Depth layers generated: {w}x{h}")
    return {
        "subject_png": subject_buf.tobytes(),
        "background_png": bg_buf.tobytes(),
        "width": w,
        "height": h,
        "output_dir": str(out_dir),
    }
