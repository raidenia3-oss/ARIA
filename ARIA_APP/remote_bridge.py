# -*- coding: utf-8 -*-
"""Puente remoto ARIA <-> asagi (solo salida, sin puertos ni escucha).

Soporta pairing por codigo, tokens con scopes, auditoria y cola offline.
"""
from __future__ import annotations

import json
import os
import time
import uuid
import urllib.request
import urllib.parse
from typing import Any, Dict, Optional, List

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TOKEN_FILE = os.path.join(DATA_DIR, "bridge_token.txt")
SCOPES_FILE = os.path.join(DATA_DIR, "bridge_scopes.json")
AUDIT_FILE = os.path.join(DATA_DIR, "bridge_audit.jsonl")
QUEUE_FILE = os.path.join(DATA_DIR, "bridge_queue.json")


def _ensure_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _url() -> Optional[str]:
    u = os.environ.get("ARIA_BRIDGE_URL", "").strip()
    return u if u else None


def _audit(action: str, detail: Any = None) -> None:
    _ensure_dir()
    entry = {"ts": time.time(), "action": action, "detail": detail}
    try:
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def pair_request() -> Dict[str, Any]:
    """Genera un codigo de emparejamiento one-time."""
    _ensure_dir()
    code = uuid.uuid4().hex[:8].upper()
    entry = {"code": code, "created": time.time(), "used": False}
    path = os.path.join(DATA_DIR, "bridge_pair_code.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(entry))
    _audit("pair_request", {"code": code})
    return {"ok": True, "code": code, "expires_in": 300}


def pair_confirm(code: str, token: str, scopes: Optional[List[str]] = None) -> Dict[str, Any]:
    _ensure_dir()
    path = os.path.join(DATA_DIR, "bridge_pair_code.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
    except Exception:
        return {"ok": False, "error": "sin codigo pendiente"}
    if entry.get("used"):
        return {"ok": False, "error": "codigo ya usado"}
    if entry.get("code") != (code or "").upper():
        return {"ok": False, "error": "codigo invalido"}
    if time.time() - entry.get("created", 0) > 300:
        return {"ok": False, "error": "codigo expirado"}
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(token)
    scopes = scopes or ["read"]
    with open(SCOPES_FILE, "w", encoding="utf-8") as f:
        json.dump(scopes, f)
    entry["used"] = True
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entry, f)
    _audit("pair_confirm", {"scopes": scopes})
    return {"ok": True, "scopes": scopes}


def get_token() -> Optional[str]:
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


def get_scopes() -> List[str]:
    try:
        with open(SCOPES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _queue_load() -> List[Dict[str, Any]]:
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _queue_save(q: List[Dict[str, Any]]) -> None:
    _ensure_dir()
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(q, f)


def push(payload: Dict[str, Any], token: Optional[str] = None) -> Dict[str, Any]:
    u = _url()
    tok = token or get_token()
    if not u:
        _queue_save(_queue_load() + [{"payload": payload, "ts": time.time()}])
        _audit("push_queued", {"reason": "no_url"})
        return {"ok": False, "queued": True, "error": "ARIA_BRIDGE_URL no configurado"}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(u + "/push", data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            # drenar cola
            q = _queue_load()
            sent = 0
            for item in q:
                try:
                    d = json.dumps(item["payload"], ensure_ascii=False).encode("utf-8")
                    rq = urllib.request.Request(u + "/push", data=d, method="POST")
                    rq.add_header("Content-Type", "application/json; charset=utf-8")
                    if tok:
                        rq.add_header("Authorization", "Bearer " + tok)
                    urllib.request.urlopen(rq, timeout=15).read()
                    sent += 1
                except Exception:
                    break
            if sent:
                _queue_save(q[sent:])
            _audit("push_ok", {"queued_drained": sent})
            return {"ok": True, "status": r.status, "body": r.read().decode("utf-8", "replace"), "drained": sent}
    except Exception as exc:
        _queue_save(_queue_load() + [{"payload": payload, "ts": time.time()}])
        _audit("push_queued", {"reason": str(exc)})
        return {"ok": False, "queued": True, "error": str(exc)}


def pull(channel: str = "default", token: Optional[str] = None) -> Dict[str, Any]:
    u = _url()
    tok = token or get_token()
    if not u:
        return {"ok": False, "error": "ARIA_BRIDGE_URL no configurado"}
    req = urllib.request.Request(u + "/pull?channel=" + urllib.parse.quote(channel), method="GET")
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return {"ok": True, "status": r.status, "data": json.loads(raw)}
            except Exception:
                return {"ok": True, "status": r.status, "data": raw}
    except Exception as exc:
        _audit("pull_fail", {"error": str(exc)})
        return {"ok": False, "error": str(exc)}


def audit_tail(n: int = 20) -> List[Dict[str, Any]]:
    try:
        with open(AUDIT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        out = []
        for ln in lines[-n:]:
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
        return out
    except Exception:
        return []


def queue_status() -> Dict[str, Any]:
    q = _queue_load()
    return {"ok": True, "queued": len(q), "items": q}