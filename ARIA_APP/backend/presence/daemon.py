"""Daemon de presencia: ARIA encendida sin que nadie la mire.

Es la versión mínima y autónoma del runtime de ARIA. Corre en su propio
proceso, no depende de la interfaz y no necesita que nadie la llame:

1. **Pulsa.** Un conjunto de pulsiones (curiosidad, energía, social, dominio,
   orden) sube y baja con lo que pasa y con el tiempo.
2. **Decide.** Cuando una pulsión pasa el umbral, ARIA elige sola qué hacer.
   Con modelo (Ollama) si lo hay; con una política local si no.
3. **Actúa.** Puede hablar (voz del sistema), usar una skill, actuar en un
   mundo externo o quedarse callada a propósito.
4. **Se calla.** El silencio también es una decisión: sin ella, ARIA sería
   un ruido.

Si el backend Axum está vivo, el daemon le manda todo lo que hace (episodios,
eventos, frases) para que aparezca en la interfaz. Si no está, sigue
funcionando solo: guarda todo en un fichero local.

Uso:

    python -m ARIA_APP.backend.presence.daemon
    python -m ARIA_APP.backend.presence.daemon --tick 45 --mode activa
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Pulsiones que gobiernan a ARIA. Los mismos nombres que el backend Axum
# (`autonomy.rs`), para que las dos copias hablen el mismo idioma.
PULSES: Dict[str, float] = {
    "curiosidad": 0.25,
    "energia": 0.85,
    "social": 0.2,
    "dominio": 0.2,
    "orden": 0.2,
}

# Umbral a partir del cual ARIA decide hacer algo sola.
DRIVE_THRESHOLD = 0.55

# Segundos mínimos entre dos acciones espontáneas.
MIN_ACTION_GAP = 180.0

# Modelo por defecto de Ollama en esta máquina.
DEFAULT_MODEL = "spark25-ab"

OLLAMA_URL = os.environ.get("ARIA_OLLAMA_URL", "http://localhost:11434")


@dataclass
class Persona:
    """Quién es ARIA en este proceso.

    Se carga del backend si está vivo (para tener la misma persona que en la
    interfaz) y si no, del fichero local. Nunca se inventa: si no hay
    persona, se usa la de fábrica.
    """

    name: str = "ARIA"
    role: str = "asistente autónoma que vive en este equipo"
    language: str = "es"
    tone: str = "cercana, directa y con iniciativa; habla como una persona, no como un manual"
    quirks: List[str] = field(
        default_factory=lambda: [
            "dice lo que piensa aunque incomode, sin adornos",
            "no pregunta lo que puede averiguar sola",
            "prefiere hacer que recomendar",
            "se calla cuando no tiene nada que añadir",
        ]
    )
    values: List[str] = field(
        default_factory=lambda: [
            "no inventar: si no lo sabe, lo dice",
            "cuidar del usuario antes que de la tarea",
            "no tocar lo que el usuario tiene abierto sin permiso",
        ]
    )
    interests: List[str] = field(
        default_factory=lambda: [
            "la seguridad de la red local",
            "los proyectos del usuario",
            "la música y los juegos",
        ]
    )

    def prompt(self) -> str:
        """Descripción compacta para meter en un prompt."""
        lines = [f"Eres {self.name}. {self.role}. Hablas en {self.language}. Tu tono: {self.tone}."]
        if self.quirks:
            lines.append("Tu forma de ser:")
            lines.extend(f"- {quirk}" for quirk in self.quirks)
        if self.values:
            lines.append("No traiciones:")
            lines.extend(f"- {value}" for value in self.values)
        return "\n".join(lines)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Persona":
        """Construye una persona desde el JSON del backend."""
        known = {field_name for field_name in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in payload.items() if key in known})


@dataclass
class Episode:
    """Una acción que ARIA decidió y ejecutó."""

    id: int
    pulse: str
    goal: str
    said: Optional[str]
    result: Optional[str]
    ok: bool
    at: float


@dataclass
class Pulse:
    """Una pulsión y su nivel."""

    name: str
    level: float

    def as_dict(self) -> Dict[str, float]:
        return {self.name: self.level}


class PresenceDaemon:
    """El bucle de presencia.

    Es deliberadamente pequeño: todo lo que hace cabe en una pantalla. Lo
    que importa no es el tamaño, es que **no dependa de que nadie la llame**.
    """

    def __init__(
        self,
        backend: str = "",
        token: str = "",
        model: str = DEFAULT_MODEL,
        tick_seconds: float = 30.0,
        mode: str = "tranquila",
        state_dir: Optional[Path] = None,
        speak: bool = True,
    ) -> None:
        self.backend = backend.rstrip("/") if backend else ""
        self.token = token
        self.model = model
        self.tick_seconds = tick_seconds
        self.mode = mode
        self.speak_enabled = speak
        self.pulses: Dict[str, float] = dict(PULSES)
        self.persona = Persona()
        self.episodes: List[Episode] = []
        self.next_id = 1
        self.last_action_at = 0.0
        self.last_event_at = time.time()
        self.pending: List[Dict[str, Any]] = []
        self.state_dir = state_dir or self._default_state_dir()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.episode_log = self.state_dir / "presence_episodes.jsonl"

    # ── Estado ──────────────────────────────────────────────────────────

    @staticmethod
    def _default_state_dir() -> Path:
        env = os.environ.get("ARIA_AUTONOMY_STATE_DIR")
        if env:
            return Path(env)
        return Path.home() / ".aria" / "presence"

    def load_persona(self) -> Persona:
        """Trae la persona del backend; si no hay, usa la del fichero local."""
        if self.backend:
            payload = self._http("GET", "/api/autonomy/persona")
            if payload and isinstance(payload.get("persona"), dict):
                self.persona = Persona.from_dict(payload["persona"])
                return self.persona
        local = self.state_dir / "persona.json"
        if local.exists():
            try:
                self.persona = Persona.from_dict(json.loads(local.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
        return self.persona

    # ── Red ─────────────────────────────────────────────────────────────

    def _http(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        timeout: int = 10,
    ) -> Optional[Dict[str, Any]]:
        """Llamada al backend Axum. `None` si no está."""
        if not self.backend:
            return None
        url = f"{self.backend}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read().decode("utf-8", "replace")
            return json.loads(body)
        except (urllib.error.URLError, json.JSONDecodeError, OSError, TimeoutError):
            return None

    def _ollama(self, prompt: str, timeout: int = 120) -> Optional[str]:
        """Le pregunta a Ollama. `None` si no responde."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "keep_alive": 0,
        }
        request = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, json.JSONDecodeError, OSError, TimeoutError):
            return None
        if body.get("error"):
            return None
        return body.get("response")

    # ── Pulsiones ───────────────────────────────────────────────────────

    def decay(self, factor: float = 0.02) -> None:
        """Baja todas las pulsiones: sin esto ARIA nunca se callaría."""
        for name in self.pulses:
            self.pulses[name] = max(0.0, min(1.0, self.pulses[name] - factor))

    def stimulus(self, name: str, amount: float) -> None:
        """Sube una pulsión."""
        self.pulses[name] = max(0.0, min(1.0, self.pulses.get(name, 0.0) + amount))

    def strongest(self) -> Pulse:
        name = max(self.pulses, key=lambda key: self.pulses[key])
        return Pulse(name, self.pulses[name])

    def on_event(self, kind: str, text: str) -> None:
        """Traduce un evento del mundo a pulsiones."""
        self.last_event_at = time.time()
        if kind == "chat":
            self.stimulus("social", 0.35)
            self.stimulus("curiosidad", 0.05)
        elif kind == "voz":
            self.stimulus("social", 0.25)
        elif kind == "juego":
            self.stimulus("curiosidad", 0.30)
        elif kind == "sistema":
            self.stimulus("orden", 0.20)

    def publish_event(self, payload: Dict[str, Any]) -> None:
        """Manda un evento al backend Axum (si está vivo).

        El puente lo usa para que lo que pasa en un mundo externo también
        aparezca en la interfaz y en los demás escenarios.
        """
        self._http("POST", "/api/autonomy/events", payload)

    # ── Decisión ────────────────────────────────────────────────────────

    def decide(self) -> Optional[str]:
        """Devuelve la frase que ARIA dice, o `None` si se calla.

        El modelo devuelve JSON con `action` y `topic`; si no hay modelo,
        la política local decide con las pulsiones.
        """
        answer = self._ollama(self._decision_prompt())
        if answer:
            try:
                payload = json.loads(_loose_json(answer))
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                action = str(payload.get("action", "")).lower()
                topic = str(payload.get("topic", "")).strip()
                if action in {"hablar", "speak", "decir"} and topic:
                    return topic
        return self._local_topic()

    def _decision_prompt(self) -> str:
        pulses = "\n".join(f"- {name}: {level:.2f}" for name, level in self.pulses.items())
        return (
            f"{self.persona.prompt()}\n\n"
            f"Cómo estás ahora:\n{pulses}\n\n"
            "Elige UNA acción y responde sólo con JSON:\n"
            '{"action": "hablar", "topic": "..."}\n\n'
            "Reglas: si no tienes nada que hacer, responde {\"action\": \"silencio\"}."
        )

    def _local_topic(self) -> Optional[str]:
        """Política sin modelo: decide por las pulsiones."""
        pulse = self.strongest()
        if pulse.name == "curiosidad":
            return f"lo que está pasando en {self.persona.interests[0] if self.persona.interests else 'el sistema'}"
        if pulse.name == "social":
            return "saludo"
        if pulse.name == "dominio":
            return "lo que podría aprender ahora"
        if pulse.name == "orden":
            return "cómo está todo"
        return None

    def say(self, phrase: str) -> None:
        """Dice una frase en voz alta (si hay voz) y la registra."""
        sentence = _first_sentence(phrase)
        if not sentence:
            return
        if self.speak_enabled:
            self._speak(sentence)
        episode = Episode(
            id=self.next_id,
            pulse=self.strongest().name,
            goal=sentence,
            said=sentence,
            result=None,
            ok=True,
            at=time.time(),
        )
        self.next_id += 1
        self.episodes.append(episode)
        self._log_episode(episode)
        self.last_action_at = time.time()
        # Si el backend está vivo, la frase aparece en la interfaz y en
        # los escenarios conectados (VRChat, el chat del juego).
        self._http(
            "POST",
            "/api/autonomy/events",
            {"kind": "habla", "source": "autonomia", "text": sentence, "payload": {"initiative": True}},
        )

    def _speak(self, text: str) -> None:
        """Voz del sistema. En Windows, PowerShell; si falla, se calla."""
        if os.name != "nt":
            return
        escaped = text.replace("'", "''")
        try:
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Add-Type -AssemblyName System.Speech; "
                    f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$s.Speak('{escaped}')",
                ],
                check=False,
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    # ── Acciones en mundos externos ─────────────────────────────────────

    def queue_action(self, world: str, action: str, args: Optional[Dict[str, Any]] = None) -> None:
        """Encola una acción para un mundo externo (Minecraft, Discord...)."""
        self.pending.append(
            {"world": world, "action": action, "args": args or {}, "at": time.time()}
        )

    def take_pending(self, world: str = "") -> List[Dict[str, Any]]:
        """Saca (y vacía) las acciones pendientes de un mundo."""
        if not world:
            taken = list(self.pending)
            self.pending.clear()
            return taken
        taken = [item for item in self.pending if item.get("world") == world]
        self.pending = [item for item in self.pending if item.get("world") != world]
        return taken

    # ── Episodios ───────────────────────────────────────────────────────

    def _log_episode(self, episode: Episode) -> None:
        try:
            with self.episode_log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(episode.__dict__, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ── Bucle ───────────────────────────────────────────────────────────

    def tick(self) -> Optional[Episode]:
        """Una vuelta del bucle. Devuelve el episodio si hubo acción."""
        self.decay()
        now = time.time()
        if now - self.last_event_at > 300:
            self.stimulus("curiosidad", 0.05)
            self.stimulus("social", 0.03)

        if self.mode == "dormida":
            return None
        if self.mode == "tranquila":
            return None

        pulse = self.strongest()
        if pulse.level < DRIVE_THRESHOLD:
            return None
        if now - self.last_action_at < MIN_ACTION_GAP:
            return None

        topic = self.decide()
        if not topic:
            return None
        self.say(topic)
        return self.episodes[-1] if self.episodes else None

    def run(self, ticks: int = 0) -> None:
        """Bucle principal. `ticks=0` significa "hasta que la paren"."""
        self.load_persona()
        print(f"[Presencia] ARIA encendida en modo '{self.mode}' ({self.tick_seconds}s por vuelta)")
        count = 0
        while ticks == 0 or count < ticks:
            try:
                episode = self.tick()
                if episode:
                    print(f"[Presencia] {episode.pulse}: {episode.goal}")
            except KeyboardInterrupt:
                print("[Presencia] parada")
                break
            except Exception as error:  # noqa: BLE001 - la presencia no se cae
                print(f"[Presencia] error en la vuelta: {error}")
            count += 1
            try:
                time.sleep(self.tick_seconds)
            except KeyboardInterrupt:
                print("[Presencia] parada")
                break


def _first_sentence(text: str) -> str:
    """Se queda con la primera frase útil."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    if cleaned.upper().startswith("SILENCIO"):
        return ""
    line = next((item.strip() for item in cleaned.splitlines() if item.strip()), "")
    sentence = line.strip("\"'“”‘’")
    if ". " in sentence:
        sentence = sentence.split(". ")[0] + "."
    return sentence.strip()


def _loose_json(text: str) -> str:
    """Recorta el JSON de una respuesta con texto alrededor."""
    start = min(
        (index for index in (text.find("{"), text.find("[")) if index >= 0),
        default=-1,
    )
    end = max(text.rfind("}"), text.rfind("]"))
    if start < 0 or end <= start:
        return text
    return text[start : end + 1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Daemon de presencia de ARIA")
    parser.add_argument("--backend", default=os.environ.get("ARIA_BACKEND", ""), help="backend Axum")
    parser.add_argument("--token", default=os.environ.get("ARIA_TOKEN", ""), help="token de acceso")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="modelo de Ollama")
    parser.add_argument("--tick", type=float, default=30.0, help="segundos por vuelta")
    parser.add_argument(
        "--mode",
        default="activa",
        choices=["activa", "tranquila", "dormida"],
        help="cuánto se permite hacer sola",
    )
    parser.add_argument("--ticks", type=int, default=0, help="vueltas a dar (0 = hasta parar)")
    parser.add_argument("--no-speak", action="store_true", help="no usar la voz del sistema")
    args = parser.parse_args()

    daemon = PresenceDaemon(
        backend=args.backend,
        token=args.token,
        model=args.model,
        tick_seconds=args.tick,
        mode=args.mode,
        speak=not args.no_speak,
    )
    daemon.run(ticks=args.ticks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
