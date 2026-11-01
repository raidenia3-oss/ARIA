from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, urljoin

try:
    import httpx
except Exception:
    httpx = None

USER_AGENT = "ARIA-Explorer/1.0 (+local)"

class HttpClient:
    """Pure outbound-only HTTP(S) client. No server/listen bindings."""
    def __init__(self, timeout: float = 10.0, max_bytes: int = 1_000_000, max_redirects: int = 3) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects

    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        h = {"User-Agent": USER_AGENT}
        if headers:
            h.update(headers)
        try:
            if httpx is not None:
                with httpx.Client(follow_redirects=True, timeout=self.timeout, max_redirects=self.max_redirects) as c:
                    r = c.get(url, headers=h)
                    data = r.read()
                    text = data.decode("utf-8", errors="replace")[: self.max_bytes]
                    return {"status": r.status_code, "ok": r.is_success, "text": text, "content_type": r.headers.get("content-type"), "url": str(r.url)}
            else:
                from urllib.request import Request, urlopen
                req = Request(url, headers=h)
                with urlopen(req, timeout=self.timeout) as r:
                    data = r.read(self.max_bytes)
                    text = data.decode("utf-8", errors="replace")
                    ct = r.headers.get("Content-Type") if hasattr(r, "headers") else None
                    return {"status": getattr(r, "status", 200), "ok": True, "text": text, "content_type": ct, "url": url}
        except Exception as e:
            return {"status": 0, "ok": False, "error": str(e), "text": ""}

client = HttpClient()
def get_client() -> HttpClient:
    return client
