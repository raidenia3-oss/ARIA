# -*- coding: utf-8 -*-
"""ARIA - Generacion de imagenes LOCAL (Stable Diffusion en proceso, Regla v2).

Idea robada de ComfyUI/diffusers pero SIN su servidor: usa la libreria `diffusers`
dentro del mismo proceso de ARIA (sin puerto, sin subprocess, sin red una vez bajado
el modelo). Resultado: imagenes SIN watermark, sin rate-limit, 100% en tu PC. Reemplaza
a Pollinations para el avatar y cualquier imagen.

Hardware de Daniel: sin GPU, 15 GB RAM -> corre en CPU (lento, ~1-2 min/imagen a 512px,
pero funciona y queda limpio). El modelo SD1.5 se baja UNA vez (~4 GB) a la cache de HF.

API compatible con gen_imagen.generar(prompt, w, h, archivo, seed) -> {"ok": True, ...}
asi chibi_art y gen_imagen pueden usarlo como proveedor preferido.

Requiere: diffusers, torch, transformers, accelerate.
"""
import os

MODELO_DEF = os.environ.get("ARIA_SD_MODEL", "runwayml/stable-diffusion-v1-5")
# negativo por defecto: mata watermark/texto/deformidades
NEGATIVO_DEF = ("watermark, signature, text, logo, caption, username, blurry, lowres, "
                "extra limbs, extra fingers, deformed, bad anatomy, jpeg artifacts, "
                "red eyes, orange eyes, animal ears, cat ears, fox ears, extra ears")

_PIPE = None
_PIPE_ID = None


def disponible():
    try:
        import importlib.util
        if importlib.util.find_spec("torch") is None:
            return False
        if importlib.util.find_spec("diffusers") is None:
            return False
        import subprocess, sys
        r = subprocess.run(
            [sys.executable, "-c", "import torch, diffusers"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def _dim8(x, minimo=384):
    """SD necesita dimensiones multiplo de 8 y un minimo razonable."""
    x = max(int(minimo), int(x))
    return x - (x % 8)


def _pipeline(modelo):
    """Carga (perezosa, cacheada) el pipeline en CPU con ahorro de memoria."""
    global _PIPE, _PIPE_ID
    if _PIPE is not None and _PIPE_ID == modelo:
        return _PIPE
    import torch
    from diffusers import StableDiffusionPipeline
    pipe = StableDiffusionPipeline.from_pretrained(
        modelo, torch_dtype=torch.float32, safety_checker=None)
    pipe = pipe.to("cpu")
    try:
        pipe.enable_attention_slicing()     # menos RAM
    except Exception:
        pass
    _PIPE, _PIPE_ID = pipe, modelo
    return pipe


def generar(prompt, w=512, h=512, archivo=None, seed=0, steps=24,
            modelo=None, negativo=None):
    """Genera una imagen local y la guarda. Devuelve {'ok': True, ...} o {'error': ...}."""
    if not disponible():
        return {"error": "falta diffusers/torch "
                         "(pip install diffusers transformers accelerate torch)"}
    import torch
    modelo = modelo or MODELO_DEF
    # genera a >=512 para calidad y luego reescala a lo pedido
    gw, gh = _dim8(max(512, w)), _dim8(max(512, h))
    try:
        pipe = _pipeline(modelo)
        g = torch.Generator("cpu").manual_seed(int(seed) & 0x7FFFFFFF)
        img = pipe(prompt, negative_prompt=negativo or NEGATIVO_DEF,
                   width=gw, height=gh, num_inference_steps=int(steps),
                   guidance_scale=7.0, generator=g).images[0]
        if (w, h) != (gw, gh):
            img = img.resize((int(w), int(h)))
        if archivo:
            os.makedirs(os.path.dirname(os.path.abspath(archivo)) or ".", exist_ok=True)
            img.save(archivo)
        return {"ok": True, "archivo": archivo, "proveedor": "local-diffusers",
                "modelo": modelo, "sin_watermark": True}
    except Exception as exc:
        return {"error": "generacion local fallo: %s" % exc}


def liberar():
    """Suelta el pipeline de memoria (util en 15 GB RAM si ya no generas)."""
    global _PIPE, _PIPE_ID
    _PIPE, _PIPE_ID = None, None
    try:
        import gc
        gc.collect()
    except Exception:
        pass
    return {"ok": True}
