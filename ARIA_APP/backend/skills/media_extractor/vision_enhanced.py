import os
import urllib.parse
import urllib.request
from collections import Counter
from io import BytesIO
from typing import Any, Dict, List

import numpy as np
from PIL import Image


def analyze_image_bytes(data: bytes) -> Dict[str, Any]:
    img = Image.open(BytesIO(data)).convert("RGB")
    arr = np.asarray(img, dtype=np.float32)
    h, w, _ = arr.shape
    flat = arr.reshape(-1, 3)
    brightness = float(arr.mean() / 255.0)
    contrast = float(arr.std() / 255.0)
    q = (flat // 32).astype(np.uint8)
    keys = q[:, 0].astype(int) * 1024 + q[:, 1].astype(int) * 32 + q[:, 2].astype(int)
    dominant = Counter(keys.tolist()).most_common(5)
    palette = []
    for key, count in dominant:
        r = (key // 1024) * 32 + 16
        g = ((key // 32) % 32) * 32 + 16
        b = (key % 32) * 32 + 16
        palette.append({"rgb": (r, g, b), "ratio": round(count / len(keys), 4)})
    gray = arr.mean(axis=2)
    gx = np.abs(np.diff(gray, axis=1))
    gy = np.abs(np.diff(gray, axis=0))
    edge_density = float((gx.mean() + gy.mean()) / 255.0)
    return {
        "size": [w, h],
        "aspect_ratio": round(w / h, 3),
        "brightness": round(brightness, 4),
        "contrast": round(contrast, 4),
        "edge_density": round(edge_density, 4),
        "palette": palette,
    }


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    url = str(params.get("url", "")).strip()
    if not url:
        return {"status": "error", "error": "url vacia"}
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = r.read()
        return {"status": "ok", "url": url, "analysis": analyze_image_bytes(data)}
    except Exception as e:
        return {"status": "error", "url": url, "error": str(e)}
