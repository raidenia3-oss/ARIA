#!/usr/bin/env python
"""Puente de mundos de ARIA: el cuerpo de ARIA fuera del servidor.

## Qué es esto

Neuro-sama juega a Minecraft porque el juego le *habla*: un controlador le
manda el estado (dónde está, qué ve, qué lleva) y ella contesta con
acciones tipadas. Eso es el protocolo que publica el `neuro-sdk` de Vedal, y
es el mismo que usa aquí el bus de mundos del backend Axum
(`v6/axum-poc/src/world.rs`).

Este script es el otro lado de ese protocolo. Se registra como un mundo,
publica lo que ve y ejecuta lo que ARIA le pide:

    POST /api/worlds                     -> registrarse con sus capacidades
    POST /api/worlds/<id>/context        -> publicar lo que está pasando
    GET  /api/worlds/<id>/pending        -> recoger las acciones pendientes
    POST /api/worlds/<id>/bridge         -> avisar de que sigue conectado

## Mundos que trae

* **VRChat** — real. Habla por OSC con el avatar (chatbox, expresiones y
  parámetros del avatar), que es el mismo protocolo que usa el avatar de
  VIREA. Publica si VRChat está abierto y en qué mundo está.
* **Minecraft** — real si hay un servidor configurado y `mineflayer` está
  instalado (`scripts/minecraft_bridge.mjs`). Publica posición, salud,
  inventario y bloques cercanos; ejecuta moverse, mirar, hablar, cavar y
  fabricar.
* **Simulador** — para probar el bus sin nada instalado. Publica un estado
  inventado y **lo dice**: en el contexto va `"simulado": true`.

## Regla que no se rompe

Este script **no cierra nada del usuario**. Nunca mata procesos por nombre:
sólo lee si VRChat o el juego están abiertos, y si algún día cierra algo,
cierra únicamente al hijo que él mismo haya creado.

## Uso

    python scripts/aria_world_bridge.py --mundos vrchat,minecraft
    python scripts/aria_world_bridge.py --mundos simulador --una-vuelta
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

DEFAULT_HOST = os.environ.get("ARIA_BACKEND_URL", "http://127.0.0.1:8002")
DEFAULT_USERNAME = os.environ.get("ARIA_USERNAME", "aria-control-center")
VRCHAT_OSC_HOST = "127.0.0.1"
VRCHAT_OSC_PORT = 9000
VRCHAT_IMAGE_NAME = "VRChat.exe"


# --------------------------------------------------------------------------- #
# Cliente del backend
# --------------------------------------------------------------------------- #


class AriaClient:
    """Cliente mínimo del backend de ARIA (sólo biblioteca estándar)."""

    def __init__(self, base_url: str = DEFAULT_HOST, username: str = DEFAULT_USERNAME) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.token: str | None = None

    # -- HTTP ------------------------------------------------------------- #

    def _request(self, method: str, path: str, payload: Any = None, timeout: float = 10.0) -> Any:
        url = f"{self.base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body}

    def login(self) -> bool:
        try:
            payload = self._request("POST", "/api/auth/login", {"username": self.username})
        except (urllib.error.URLError, OSError) as error:
            print(f"[puente] no se pudo conectar con {self.base_url}: {error}", file=sys.stderr)
            return False
        if not isinstance(payload, dict):
            return False
        token = payload.get("token") or payload.get("access_token") or payload.get("api_key")
        if not token:
            print("[puente] el backend no devolvió token", file=sys.stderr)
            return False
        self.token = str(token)
        print(f"[puente] conectado a {self.base_url}")
        return True

    def register(self, world_id: str, kind: str, label: str, capabilities: list[dict]) -> bool:
        try:
            self._request(
                "POST",
                "/api/worlds",
                {
                    "id": world_id,
                    "kind": kind,
                    "label": label,
                    "capabilities": capabilities,
                },
            )
        except (urllib.error.URLError, OSError) as error:
            print(f"[puente] no se pudo registrar '{world_id}': {error}", file=sys.stderr)
            return False
        return True

    def publish_context(self, world_id: str, context: dict) -> bool:
        try:
            self._request("POST", f"/api/worlds/{world_id}/context", {"context": context})
            return True
        except (urllib.error.URLError, OSError) as error:
            print(f"[puente] no se pudo publicar el estado de '{world_id}': {error}", file=sys.stderr)
            return False

    def bridge_state(self, world_id: str, connected: bool, status: str) -> None:
        try:
            self._request(
                "POST",
                f"/api/worlds/{world_id}/bridge",
                {"connected": connected, "status": status},
            )
        except (urllib.error.URLError, OSError):
            pass

    def take_pending(self, world_id: str) -> list[dict]:
        try:
            payload = self._request("GET", f"/api/worlds/{world_id}/pending")
        except (urllib.error.URLError, OSError):
            return []
        if not isinstance(payload, dict):
            return []
        actions = payload.get("actions") or []
        return [a for a in actions if isinstance(a, dict)]

    def send_event(self, kind: str, source: str, text: str, payload: dict | None = None) -> None:
        try:
            self._request(
                "POST",
                "/api/autonomy/events",
                {
                    "kind": kind,
                    "source": source,
                    "text": text,
                    "payload": payload or {},
                },
            )
        except (urllib.error.URLError, OSError):
            pass


# --------------------------------------------------------------------------- #
# OSC mínimo (VRChat)
# --------------------------------------------------------------------------- #


class OscClient:
    """Emisor OSC por UDP, sólo biblioteca estándar.

    VRChat habla OSC en 127.0.0.1:9000: ahí se escriben el chatbox del
    avatar, sus expresiones y sus parámetros. Es el mismo canal que usa el
    avatar de VIREA para hablar en VRChat.
    """

    def __init__(self, host: str = VRCHAT_OSC_HOST, port: int = VRCHAT_OSC_PORT) -> None:
        self.host = host
        self.port = port
        self._socket: socket.socket | None = None

    def _ensure_socket(self) -> socket.socket:
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self._socket

    @staticmethod
    def _encode_string(value: str) -> bytes:
        raw = value.encode("utf-8") + b"\x00"
        raw += b"\x00" * (4 - len(raw) % 4)
        return raw

    @staticmethod
    def _encode_int(value: int) -> bytes:
        return struct.pack(">i", int(value))

    @staticmethod
    def _encode_float(value: float) -> bytes:
        return struct.pack(">f", float(value))

    def send(self, address: str, *args: Any) -> bool:
        payload = bytearray(self._encode_string(address))
        payload += self._encode_string(",".join(_osc_type(arg) for arg in args))
        for arg in args:
            if isinstance(arg, bool):
                payload += struct.pack(">?", arg)
            elif isinstance(arg, int):
                payload += self._encode_int(arg)
            elif isinstance(arg, float):
                payload += self._encode_float(arg)
            else:
                payload += self._encode_string(str(arg))
        try:
            self._ensure_socket().sendto(bytes(payload), (self.host, self.port))
            return True
        except OSError:
            return False

    def port_open(self) -> bool:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.settimeout(0.2)
        try:
            # Un datagrama vacío no molesta a VRChat y nos dice si el puerto
            # está abierto (si no, da ICMP port unreachable).
            probe.sendto(b"\x00\x00", (self.host, self.port))
            probe.recvfrom(64)
            return True
        except OSError:
            return False
        finally:
            probe.close()


def _osc_type(value: Any) -> str:
    if isinstance(value, bool):
        return "T" if value else "F"
    if isinstance(value, int):
        return "i"
    if isinstance(value, float):
        return "f"
    return "s"


# --------------------------------------------------------------------------- #
# Utilidades del sistema (sólo lectura)
# --------------------------------------------------------------------------- #


def process_running(image_name: str) -> bool:
    """¿Está abierto el proceso? Sólo mira: nunca termina nada."""
    system = platform.system()
    if system == "Windows":
        tasklist = shutil.which("tasklist")
        if not tasklist:
            return False
        try:
            result = subprocess.run(
                [tasklist, "/FI", f"IMAGENAME eq {image_name}", "/NH"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return image_name.lower() in result.stdout.lower()
    if system == "Darwin":
        try:
            result = subprocess.run(
                ["pgrep", "-x", image_name.replace(".exe", "")],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0
    pgrep = shutil.which("pgrep")
    if not pgrep:
        return False
    try:
        result = subprocess.run(
            [pgrep, "-f", image_name.replace(".exe", "")],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


# --------------------------------------------------------------------------- #
# Mundos
# --------------------------------------------------------------------------- #


@dataclass
class World:
    """Un mundo que ARIA puede visitar."""

    id: str
    kind: str
    label: str
    capabilities: list[dict]
    detect: Callable[[], bool]
    context: Callable[[], dict]
    act: Callable[[str, dict], str]
    describe: str = ""

    def publish(self, client: AriaClient) -> bool:
        connected = self.detect()
        payload = self.context()
        payload["conectado"] = connected
        if self.describe:
            payload["nota"] = self.describe
        client.publish_context(self.id, payload)
        return connected


def _capability(name: str, description: str, params: list[str] | None = None) -> dict:
    return {"name": name, "description": description, "params": params or []}


# ---- VRChat --------------------------------------------------------------- #

VRCHAT_EXPRESSIONS = {
    "alegre": 1,
    "alegre_2": 1,
    "curiosa": 2,
    "concentrada": 3,
    "neutra": 0,
    "burlona": 4,
}


def build_vrchat_world(osc: OscClient) -> World:
    state: dict[str, Any] = {"ultimo_texto": "", "ultima_expresion": "neutra"}

    def detect() -> bool:
        return process_running(VRCHAT_IMAGE_NAME)

    def context() -> dict:
        return {
            "avatar": "VRChat" if detect() else "sin abrir",
            "osc": f"{osc.host}:{osc.port}",
            "ultimo_mensaje": state["ultimo_texto"],
            "expresion": state["ultima_expresion"],
        }

    def act(action: str, args: dict) -> str:
        if action in ("chatbox.say", "say", "chat.say"):
            text = str(args.get("text", "")).strip()
            if not text:
                return "sin texto"
            state["ultimo_texto"] = text
            osc.send("/chatbox/typing", True)
            ok = osc.send("/chatbox/input", text, True)
            return "escrito en el chatbox" if ok else "VRChat no respondió"
        if action in ("expression.set", "expression"):
            expression = str(args.get("expression", "neutra"))
            state["ultima_expresion"] = expression
            index = VRCHAT_EXPRESSIONS.get(expression, 0)
            osc.send(f"/expression/{index}", index)
            return f"expresión {expression}"
        if action in ("parameter.set", "avatar.parameter"):
            name = str(args.get("name", ""))
            value = args.get("value", 0)
            if not name:
                return "falta el nombre del parámetro"
            if isinstance(value, bool):
                osc.send(f"/avatar/parameters/{name}", value)
            elif isinstance(value, int):
                osc.send(f"/avatar/parameters/{name}", value)
            elif isinstance(value, float):
                osc.send(f"/avatar/parameters/{name}", value)
            else:
                osc.send(f"/avatar/parameters/{name}", str(value))
            return f"parámetro {name}"
        return f"acción no soportada: {action}"

    return World(
        id="vrchat",
        kind="avatar",
        label="VRChat",
        capabilities=[
            _capability("chatbox.say", "Escribir en el chatbox del avatar", ["text"]),
            _capability("expression.set", "Cambiar la expresión del avatar", ["expression"]),
            _capability(
                "parameter.set",
                "Mover un parámetro del avatar",
                ["name", "value"],
            ),
        ],
        detect=detect,
        context=context,
        act=act,
        describe="Puente OSC real: 127.0.0.1:9000",
    )


# ---- Minecraft ------------------------------------------------------------ #

MINECRAFT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minecraft_bridge.mjs")


def build_minecraft_world() -> World:
    """Puente de Minecraft vía `mineflayer` (Node).

    El script de Node es hijo de este proceso: si el puente termina, el
    hijo termina con él, y sólo se cierra a quien este puente creó.
    """

    child: dict[str, Any] = {"process": None, "context": {}, "log": []}

    def node_available() -> bool:
        if not shutil.which("node"):
            return False
        return os.path.isfile(MINECRAFT_SCRIPT)

    def detect() -> bool:
        process = child.get("process")
        return process is not None and process.poll() is None

    def ensure_child() -> None:
        if detect():
            return
        if not node_available():
            return
        try:
            process = subprocess.Popen(
                ["node", MINECRAFT_SCRIPT],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError:
            return
        child["process"] = process

    def read_lines() -> None:
        process = child.get("process")
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                child["log"].append(line)
                continue
            if isinstance(payload, dict) and "context" in payload:
                child["context"] = payload["context"]
            else:
                child["log"].append(line)

    def context() -> dict:
        ensure_child()
        read_lines()
        data = dict(child.get("context") or {})
        data.setdefault("estado", "esperando puente")
        return data

    def act(action: str, args: dict) -> str:
        process = child.get("process")
        if process is None or process.poll() is not None:
            return "no hay puente de Minecraft conectado"
        assert process.stdin is not None
        try:
            process.stdin.write(json.dumps({"action": action, "args": args}) + "\n")
            process.stdin.flush()
        except (OSError, ValueError) as error:
            return f"no se pudo enviar la acción: {error}"
        return f"enviada al puente: {action}"

    return World(
        id="minecraft",
        kind="juego",
        label="Minecraft",
        capabilities=[
            _capability("chat.say", "Escribir en el chat del juego", ["text"]),
            _capability("move", "Ir a un punto", ["x", "y", "z"]),
            _capability("look", "Mirar hacia", ["x", "y", "z"]),
            _capability("dig", "Cavar un bloque", ["block"]),
            _capability("craft", "Fabricar un objeto", ["item"]),
            _capability("observe", "Mirar alrededor y describir", []),
        ],
        detect=detect,
        context=context,
        act=act,
        describe="Puente mineflayer (Node) o simulador",
    )


# ---- Simulador ------------------------------------------------------------ #


def build_simulator_world() -> World:
    """Un mundo de mentira, pero que lo dice.

    Sirve para probar el bus entero (publicar estado, pedir acciones,
    ejecutarlas) sin tener Minecraft ni VRChat abiertos. El contexto lleva
    `"simulado": true` para que nadie lo confunda con un mundo real.
    """

    tick = {"n": 0, "ultima": ""}

    def detect() -> bool:
        return True

    def context() -> dict:
        tick["n"] += 1
        return {
            "simulado": True,
            "posicion": {"x": tick["n"], "y": 64, "z": 0},
            "salud": 20,
            "inventario": ["pico", "manzana"],
            "bloques_cercanos": ["piedra", "madera"],
            "ultima_accion": tick["ultima"],
        }

    def act(action: str, args: dict) -> str:
        tick["ultima"] = action
        return f"simulado: {action} {json.dumps(args, ensure_ascii=False)}"

    return World(
        id="simulador",
        kind="juego",
        label="Simulador",
        capabilities=[
            _capability("chat.say", "Escribir en el chat del juego", ["text"]),
            _capability("move", "Ir a un punto", ["x", "y", "z"]),
            _capability("look", "Mirar hacia", ["x", "y", "z"]),
            _capability("dig", "Cavar un bloque", ["block"]),
            _capability("craft", "Fabricar un objeto", ["item"]),
            _capability("observe", "Mirar alrededor y describir", []),
        ],
        detect=detect,
        context=context,
        act=act,
        describe="Mundo simulado para pruebas del bus",
    )


# --------------------------------------------------------------------------- #
# Bucle principal
# --------------------------------------------------------------------------- #


def build_worlds(names: list[str]) -> list[World]:
    worlds: list[World] = []
    for name in names:
        if name == "vrchat":
            worlds.append(build_vrchat_world(OscClient()))
        elif name == "minecraft":
            worlds.append(build_minecraft_world())
        elif name == "simulador":
            worlds.append(build_simulator_world())
        else:
            print(f"[puente] mundo desconocido: {name}", file=sys.stderr)
    return worlds


def run_once(client: AriaClient, worlds: list[World]) -> int:
    """Una vuelta: publica el estado y ejecuta lo pendiente."""
    executed = 0
    for world in worlds:
        connected = world.publish(client)
        client.bridge_state(world.id, connected, "conectado" if connected else "sin conectar")
        for action in client.take_pending(world.id):
            name = str(action.get("action", ""))
            args = action.get("args") or {}
            try:
                outcome = world.act(name, args if isinstance(args, dict) else {})
            except Exception as error:  # noqa: BLE001 - un puente no debe tumbar el bus
                outcome = f"error: {error}"
            print(f"[puente] {world.id}.{name} -> {outcome}")
            client.send_event("juego", world.id, f"{name}: {outcome}", {"world": world.id})
            executed += 1
    return executed


def main() -> int:
    parser = argparse.ArgumentParser(description="Puente de mundos de ARIA")
    parser.add_argument(
        "--mundos",
        default="vrchat,minecraft",
        help="lista de mundos separados por comas (vrchat, minecraft, simulador)",
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="URL del backend de ARIA")
    parser.add_argument("--intervalo", type=float, default=5.0, help="segundos entre vueltas")
    parser.add_argument(
        "--una-vuelta",
        action="store_true",
        help="publica el estado una vez y sale (útil para probar)",
    )
    args = parser.parse_args()

    client = AriaClient(args.host)
    if not client.login():
        return 1

    worlds = build_worlds([name.strip() for name in args.mundos.split(",") if name.strip()])
    if not worlds:
        print("[puente] no hay mundos que publicar", file=sys.stderr)
        return 1

    for world in worlds:
        client.register(world.id, world.kind, world.label, world.capabilities)
        print(f"[puente] mundo '{world.id}' registrado")

    if args.una_vuelta:
        run_once(client, worlds)
        return 0

    print(f"[puente] Publishando cada {args.intervalo}s. Ctrl+C para salir.")
    try:
        while True:
            run_once(client, worlds)
            time.sleep(max(1.0, args.intervalo))
    except KeyboardInterrupt:
        print("\n[puente] hasta luego")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
