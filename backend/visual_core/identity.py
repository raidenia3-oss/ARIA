# identity module - minimal, fail-closed
from __future__ import annotations
from typing import Any, Dict, Optional
import hashlib


class Identity:
    def __init__(self) -> None:
        self.verified = False
        self.hash: Optional[str] = None

    def register(self, passphrase: str) -> Dict[str, Any]:
        if not passphrase:
            return {"status": "invalid"}
        self.hash = hashlib.sha256(passphrase.encode('utf-8')).hexdigest()
        self.verified = True
        return {"status": "registered", "verified": True}

    def verify(self, passphrase: str) -> Dict[str, Any]:
        if not self.hash:
            return {"status": "not_registered"}
        h = hashlib.sha256(passphrase.encode('utf-8')).hexdigest()
        if h == self.hash:
            self.verified = True
            return {"status": "verified"}
        return {"status": "unauthorized"}

    def status(self) -> Dict[str, Any]:
        return {"verified": self.verified}


identity = Identity()
