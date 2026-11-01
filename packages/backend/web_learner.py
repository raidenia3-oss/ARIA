# Web learner - minimal, fail-closed
from __future__ import annotations
from typing import Any, Dict
import requests


class WebLearner:
    def __init__(self) -> None:
        pass

    def learn_url(self, url: str, timeout: int = 10) -> Dict[str, Any]:
        if not url or not url.startswith('http'):
            return {"status": "invalid"}
        try:
            r = requests.get(url, timeout=timeout, headers={'User-Agent': 'AURA-learner/1.0'})
            return {"status": "ok", "status_code": r.status_code, "length": len(r.text), "snippet": r.text[:200]}
        except Exception as e:
            return {"status": "error", "error": str(e)}


web_learner = WebLearner()
