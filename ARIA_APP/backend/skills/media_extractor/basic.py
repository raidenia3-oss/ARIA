import json
import os
import re
import urllib.parse
import urllib.request
from collections import Counter
from io import BytesIO
from typing import Any, Dict

try:
    from PIL import Image
except Exception:
    Image = None

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "media_extracts")
os.makedirs(os.path.abspath(DATA_DIR), exist_ok=True)


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("utf-8", errors="ignore")


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    url = str(params.get("url", "")).strip()
    if not url:
        return {"status": "error", "error": "url vacia"}
    result: Dict[str, Any] = {"status": "ok", "url": url, "mode": "stdlib-basic"}
    try:
        oembed = "https://www.youtube.com/oembed?url=" + urllib.parse.quote(url, safe="") + "&format=json"
        result["oembed"] = json.loads(_fetch(oembed))
    except Exception as e:
        result["oembed_error"] = str(e)
    try:
        html = _fetch(url)
        title = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        result["title"] = title.group(1).strip() if title else None
        thumb = re.search(r'property="og:image"\s+content="([^"]+)"', html, re.I)
        result["thumbnail"] = thumb.group(1) if thumb else None
        desc = re.search(r'property="og:description"\s+content="([^"]+)"', html, re.I)
        result["description"] = desc.group(1) if desc else None
    except Exception as e:
        result["html_error"] = str(e)
    thumb_url = result.get("oembed", {}).get("thumbnail_url") or result.get("thumbnail")
    if Image and thumb_url:
        try:
            with urllib.request.urlopen(thumb_url, timeout=10) as r:
                img = Image.open(BytesIO(r.read()))
            img = img.convert("RGB")
            result["image_size"] = img.size
            pixels = list(img.getdata())
            result["brightness"] = round(sum(sum(p) for p in pixels) / (len(pixels) * 3 * 255), 3)
            result["dominant_color"] = Counter(pixels).most_common(1)[0][0]
        except Exception as e:
            result["image_error"] = str(e)
    return result
