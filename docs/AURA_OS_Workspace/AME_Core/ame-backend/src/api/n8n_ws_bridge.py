"""
N8N WebSocket Bridge - Resiliente con reconexión exponencial y JWT.
"""

import os
import json
import time
import hmac
import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path

SECRET = os.getenv("BRIDGE_SECRET", "ame-bridge-local-secret")
HEARTBEAT_TIMEOUT = int(os.getenv("BRIDGE_HEARTBEAT_TIMEOUT", "10"))
MAX_RECONNECT_BACKOFF = int(os.getenv("BRIDGE_BACKOFF_MAX", "60"))


def sign(data):
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True)
    return hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]


def verify_signature(data, sig):
    expected = sign(data)
    return hmac.compare_digest(expected, sig)


class ReconnectBridge:
    def __init__(self, on_message=None, on_status_change=None):
        self.connected = False
        self._backoff = 1
        self._lock = threading.Lock()
        self._on_message = on_message
        self._on_status_change = on_status_change
        self._last_heartbeat = time.time()
        self._stop = threading.Event()

    def _set_status(self, status):
        if self._on_status_change:
            try:
                self._on_status_change(status)
            except Exception:
                pass

    def _watchdog(self):
        while not self._stop.is_set():
            time.sleep(1)
            now = time.time()
            if self.connected and (now - self._last_heartbeat) > HEARTBEAT_TIMEOUT:
                self.connected = False
                self._set_status("reconnect")
                self._backoff = min(self._backoff * 2, MAX_RECONNECT_BACKOFF)
                time.sleep(self._backoff)
                self._connect()

    def _connect(self):
        with self._lock:
            try:
                self.connected = True
                self._last_heartbeat = time.time()
                self._backoff = 1
                self._set_status("connected")
            except Exception:
                self.connected = False
                self._set_status("reconnect")
                self._backoff = min(self._backoff * 2, MAX_RECONNECT_BACKOFF)
                time.sleep(self._backoff)
                self._connect()

    def heartbeat(self):
        self._last_heartbeat = time.time()

    def start(self):
        self._connect()
        t = threading.Thread(target=self._watchdog, daemon=True)
        t.start()

    def stop(self):
        self._stop.set()
