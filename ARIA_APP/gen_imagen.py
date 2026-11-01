# -*- coding: utf-8 -*-
"""ARIA - Generador de imagenes (skill de salida, sin servidores ni deps nuevas).

Multi-proveedor con reintentos y espaciado (el tier gratis de Pollinations limita
a ~1 imagen / 15s y responde 402/429 si te pasas).

Proveedores:
  - pollinations (por defecto, SIN clave)
  - hf (HuggingFace Inference API) si defines HF_TOKEN (gratis con tu cuenta)
Seleccion: ARIA_IMG_PROVIDER, o auto: hf si hay HF_TOKEN, si no pollinations.
"""
import os
import time
import json
import urllib.parse
import urllib.request
import urllib.error

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "imagenes")
_PROVIDER = os.environ.get("ARIA_IMG_PROVIDER", "").strip().lower()
_HF_TOKEN = os.environ.get("HF_TOKEN", "").strip()
_POLL_MODEL = os.environ.get("ARIA_IMG_MODEL", "flux").strip()
_HF_MODEL = os.environ.get("ARIA_HF_MODEL", "stabilityai/stable-diffusion-xl-base-1.0").strip()


def disponible():
    return True


def _proveedor():
    if _PROVIDER:
        return _PROVIDER
    return "hf" if _HF_TOKEN else "pollinations"


def _pollinations(prompt, w, h, seed, timeout):
    base = "https://image.pollinations.ai/prompt/"
    params = {"width": w, "height": h, "nologo": "true",
              "model": _POLL_MODEL, "referrer": "aria-local"}
    if seed is not None:
        params["seed"] = int(seed)
    url = base + urllib.parse.quote(prompt) + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "ARIA-Img/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _hf(prompt, w, h, seed, timeout):
    if not _HF_TOKEN:
        raise RuntimeError("falta HF_TOKEN")
    url = "https://api-inference.huggingface.co/models/" + _HF_MODEL
    body = json.dumps({"inputs": prompt}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": "Bearer " + _HF_TOKEN,
        "Content-Type": "application/json",
        "User-Agent": "ARIA-Img/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def generar(prompt, w=640, h=640, archivo=None, seed=None, timeout=120, reintentos=4):
    prompt = (prompt or "").strip()
    if not prompt:
        return {"error": "sin prompt"}
    prov = _proveedor()
    fn = _hf if prov == "hf" else _pollinations
    try:
        os.makedirs(_DIR, exist_ok=True)
    except Exception:
        pass
    destino = archivo or os.path.join(_DIR, "aria_img_%d.jpg" % int(time.time()))
    ultimo = "?"
    for intento in range(reintentos):
        try:
            data = fn(prompt, w, h, seed, timeout)
            if data and len(data) > 500:
                with open(destino, "wb") as f:
                    f.write(data)
                return {"ok": True, "archivo": destino, "bytes": len(data),
                        "proveedor": prov, "resumen": "Imagen generada: %s" % destino}
            ultimo = "respuesta vacia"
            time.sleep(5)
        except urllib.error.HTTPError as e:
            ultimo = "HTTP %s" % e.code
            if e.code in (402, 429):          # throttle del tier gratis -> esperar y reintentar
                time.sleep(16)
                continue
            if e.code in (503, 500):          # modelo cargando (HF) -> esperar
                time.sleep(20)
                continue
            break
        except Exception as e:
            ultimo = str(e)
            time.sleep(4)
    return {"error": "fallo la generacion (%s): %s" % (prov, ultimo)}
