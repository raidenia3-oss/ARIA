"""Puente para mundos externos: Minecraft, Discord, el móvil.

Un "mundo" es cualquier cosa que tenga estado y acciones: un bot de
Minecraft, un script de Discord, la app del teléfono. El puente les da
una forma trivial de hablar con ARIA:

- ``POST /event``     → algo ha pasado en el mundo (un chat, un bloque roto).
- ``GET  /pending``   → qué tiene que hacer ARIA en ese mundo.
- ``GET  /status``    → cómo está la presencia.
- ``POST /say``       → ARIA dice algo en el mundo.

Es la misma idea que el protocolo de neuro-sdk, pero en Python y sin
dependencias: sólo la biblioteca estándar.

    python -m ARIA_APP.backend.presence.bridge --port 8765
"""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from .daemon import PresenceDaemon


class BridgeState:
    """Lo que el puente comparte con el daemon."""

    def __init__(self, daemon: PresenceDaemon) -> None:
        self.daemon = daemon
        self.lock = threading.Lock()
        self.events: List[Dict[str, Any]] = []

    def push_event(self, kind: str, source: str, text: str, payload: Dict[str, Any]) -> None:
        """Registra un evento del mundo y lo pasa al daemon."""
        with self.lock:
            self.events.append(
                {"kind": kind, "source": source, "text": text, "payload": payload, "at": _now()}
            )
            # No crece sin fin: sólo interesa lo reciente.
            if len(self.events) > 200:
                self.events = self.events[-200:]
        self.daemon.on_event(kind, text)
        # Si el backend Axum está vivo, el evento también sale por ahí: así
        # aparece en la interfaz y en los demás escenarios.
        self.daemon.publish_event(
            {"kind": kind, "source": source, "text": text, "payload": payload}
        )

    def pending(self, world: str) -> List[Dict[str, Any]]:
        return self.daemon.take_pending(world)

    def status(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "mode": self.daemon.mode,
            "pulses": dict(self.daemon.pulses),
            "persona": self.daemon.persona.name,
            "episodes": len(self.daemon.episodes),
            "pending": len(self.daemon.pending),
            "events": len(self.events),
        }


def _now() -> float:
    import time

    return time.time()


class BridgeHandler(BaseHTTPRequestHandler):
    """Peticiones del puente. Sólo stdlib."""

    state: BridgeState  # se inyecta al crear el servidor

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Silencia el log por defecto: el puente no es un servidor web."""
        return

    def _send(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8", "replace"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:  # noqa: N802 - nombre impuesto por BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/status":
            self._send(self.state.status())
            return
        if parsed.path == "/pending":
            world = (query.get("world") or [""])[0]
            self._send({"status": "ok", "actions": self.state.pending(world)})
            return
        if parsed.path == "/events":
            self._send({"status": "ok", "events": self.state.events[-50:]})
            return
        self._send({"status": "error", "error": "ruta desconocida"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        payload = self._read_json()
        if parsed.path == "/event":
            kind = str(payload.get("kind", "chat"))
            source = str(payload.get("source", "mundo"))
            text = str(payload.get("text", ""))
            extra = payload.get("payload")
            self.state.push_event(
                kind,
                source,
                text,
                extra if isinstance(extra, dict) else {},
            )
            self._send({"status": "ok"})
            return
        if parsed.path == "/say":
            phrase = str(payload.get("text", "")).strip()
            if not phrase:
                self._send({"status": "error", "error": "falta el texto"}, status=400)
                return
            self.state.daemon.say(phrase)
            self._send({"status": "ok"})
            return
        if parsed.path == "/action":
            world = str(payload.get("world", "")).strip()
            action = str(payload.get("action", "")).strip()
            if not world or not action:
                self._send({"status": "error", "error": "falta world o action"}, status=400)
                return
            args = payload.get("args")
            self.state.daemon.queue_action(
                world, action, args if isinstance(args, dict) else {}
            )
            self._send({"status": "ok"})
            return
        self._send({"status": "error", "error": "ruta desconocida"}, status=404)


class BridgeServer:
    """El puente, listo para arrancar."""

    def __init__(self, daemon: Optional[PresenceDaemon] = None, port: int = 8765) -> None:
        self.daemon = daemon or PresenceDaemon()
        self.port = port
        self.state = BridgeState(self.daemon)
        self._server: Optional[ThreadingHTTPServer] = None

    def serve_forever(self) -> None:
        """Arranca el servidor (bloqueante)."""
        handler = type("BoundBridgeHandler", (BridgeHandler,), {"state": self.state})
        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        print(f"[Puente] escuchando en http://127.0.0.1:{self.port}")
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            print("[Puente] parado")
        finally:
            self._server.server_close()

    def start_background(self) -> threading.Thread:
        """Arranca el servidor en un hilo y devuelve el hilo."""
        thread = threading.Thread(target=self.serve_forever, daemon=True)
        thread.start()
        return thread


def main() -> int:
    parser = argparse.ArgumentParser(description="Puente de mundos externos para ARIA")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--backend", default="", help="backend Axum (opcional)")
    parser.add_argument("--token", default="", help="token de acceso")
    parser.add_argument("--mode", default="activa", choices=["activa", "tranquila", "dormida"])
    args = parser.parse_args()

    daemon = PresenceDaemon(backend=args.backend, token=args.token, mode=args.mode)
    daemon.load_persona()
    BridgeServer(daemon, port=args.port).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
