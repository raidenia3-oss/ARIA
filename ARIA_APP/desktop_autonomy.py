"""La autonomía de ARIA, vista desde el escritorio.

El escritorio (PyQt5) es un escenario de la misma ARIA, y la autonomía vive
**en el proceso**: no hay núcleo en otro puerto, ni backend en Python, ni
navegador. Aquí se conecta el runtime local (`ARIA_APP.autonomy`) con las
manos que ya tenía el escritorio (`aria_va_core`), de modo que lo que ARIA
percibe, lo que tiene entre manos y lo que aprende salga de su propia
memoria, no de un servicio ajeno.

Si al runtime le faltan las manos (skills) o la cabeza (modelo), sigue
funcionando: lo que no puede hacer, lo deja escrito y lo intentará más
adelante.
"""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

ARIA_APP = Path(__file__).resolve().parent
_PROJECT_ROOT = ARIA_APP.parent
for _sys_path in (str(_PROJECT_ROOT), str(ARIA_APP)):
    if _sys_path not in sys.path:
        sys.path.insert(0, _sys_path)

from ARIA_APP.autonomy.runtime import Runtime, set_runtime  # noqa: E402

#: Cada cuánto se mira lo que ARIA está perceiving.
POLL_SECS = 10.0

#: Cada cuánto late ARIA por su cuenta y da una vuelta del runtime.
HEARTBEAT_SECS = 45.0

#: El runtime local del escritorio, con las manos del núcleo VA.
_runtime: Optional[Runtime] = None
_runtime_lock = threading.Lock()

#: El latido de ARIA, cuando está arrancado.
_heartbeat: Optional["Heartbeat"] = None
_heartbeat_lock = threading.Lock()


def runtime() -> Runtime:
    """El runtime autónomo, con skills y cerebro del núcleo VA.

    El núcleo VA (`aria_va_core`) ya está en el proceso del escritorio: sus
    skills son locales (sin red, sin subprocess) y su cerebro es local. Se
    reutilizan en vez de crear un segundo cerebro.
    """
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            brain = None
            skills = None
            try:
                from aria_va_core import get_va

                va = get_va()
                brain = getattr(va, "brain", None)
                skills = getattr(va, "skills", None)
            except Exception as exc:  # noqa: BLE001 - sin manos, pero en pie
                log.debug("autonomy: el núcleo VA no está disponible: %s", exc)
            _runtime = Runtime(skills=skills, brain=brain)
            set_runtime(_runtime)
        return _runtime


def reset_runtime() -> None:
    """Olvida el runtime del escritorio (lo vuelve a crear con las manos)."""
    global _runtime
    with _runtime_lock:
        _runtime = None
    set_runtime(None)


# ── El latido ───────────────────────────────────────────────────────────────


class Heartbeat:
    """El latido de ARIA: una vuelta del runtime cada cierto tiempo.

    Late en su propio hilo: un tick puede tardar (skills, cerebro) y la
    interfaz no puede quedarse congelada esperando. Si el runtime no está
    listo, el latido se salta el turno en vez de romper la app.
    """

    def __init__(self, interval: float = HEARTBEAT_SECS, on_beat=None) -> None:
        self.interval = float(interval)
        self.on_beat = on_beat
        self.beats = 0
        self.last_result: Optional[Dict[str, Any]] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> "Heartbeat":
        if self._thread is not None and self._thread.is_alive():
            return self
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="aria-heartbeat"
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()

    def beat(self) -> Dict[str, Any]:
        """Una vuelta real del runtime, aquí y ahora."""
        result = runtime().tick()
        self.beats += 1
        self.last_result = result
        if self.on_beat is not None:
            try:
                self.on_beat(result)
            except Exception:  # noqa: BLE001 - un oyente roto no para el latido
                pass
        return result

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self._stop.wait(self.interval):
                return
            try:
                self.beat()
            except Exception:  # noqa: BLE001 - el latido nunca tumba la app
                pass


def heartbeat() -> Optional[Heartbeat]:
    """El latido actual, si lo hay."""
    return _heartbeat


def start_heartbeat(
    interval: float = HEARTBEAT_SECS, on_beat=None
) -> Heartbeat:
    """Arranca el latido de ARIA (idempotente).

    Si ya hay un latido, solo actualiza el oyente: asi el escritorio puede
    enganchar su señal sin que el latido se quede sin hablar.
    """
    global _heartbeat
    with _heartbeat_lock:
        if _heartbeat is None:
            _heartbeat = Heartbeat(interval=interval, on_beat=on_beat)
        elif on_beat is not None:
            _heartbeat.on_beat = on_beat
        _heartbeat.start()
        return _heartbeat


def stop_heartbeat() -> None:
    """Detiene el latido de ARIA."""
    global _heartbeat
    with _heartbeat_lock:
        if _heartbeat is not None:
            _heartbeat.stop()
        _heartbeat = None


# ── Lectura para la interfaz ───────────────────────────────────────────────


def summarize(perception: Optional[Dict[str, Any]]) -> str:
    """Una línea con lo que ARIA está perceiving.

    El orden es el del prompt de decisión: primero el mundo, luego la
    gente, luego las ganas.
    """
    if not perception:
        return "Sin perception todavia."

    worlds = perception.get("worlds") or []
    connected = [w for w in worlds if w.get("connected")]
    if connected:
        where = "En " + ", ".join(str(w.get("label") or w.get("id")) for w in connected)
    elif worlds:
        where = "Ningun mundo conectado"
    else:
        where = "Sin mundos"

    audience = perception.get("audience")
    if isinstance(audience, dict) and audience.get("author"):
        who = f"{audience.get('author')} en {audience.get('channel', 'la consola')}"
    else:
        who = "nadie esperando"

    drives = perception.get("drives") or {}
    strongest = ""
    if drives:
        name, level = max(drives.items(), key=lambda pair: pair[1])
        strongest = f"gana {name} ({float(level):.2f})"

    parts = [where, who]
    if strongest:
        parts.append(strongest)
    return " · ".join(parts) + "."


def pending_goals(perception: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Lo que ARIA tiene entre manos.

    Primero lo pendiente; después lo que está esperando permiso, que sigue
    siendo suyo aunque no pueda tocarlo todavía.
    """
    if not perception:
        return []
    agenda = perception.get("agenda") or []
    pending = [item for item in agenda if item.get("state") == "pendiente"]
    waiting = [item for item in agenda if item.get("state") == "esperando"]
    return pending + waiting


def last_episode(runtime_instance: Optional[Runtime] = None) -> Dict[str, Any]:
    """Lo último que ARIA hizo, tal y como quedó en su registro."""
    instance = runtime_instance or runtime()
    try:
        episodes = instance.status().get("episodes") or []
    except Exception:  # noqa: BLE001 - la interfaz no se cae por esto
        return {}
    if not episodes:
        return {}
    last = episodes[-1]
    return dict(last) if isinstance(last, dict) else {}


def episode_line(episode: Optional[Dict[str, Any]]) -> str:
    """Una línea con lo que ARIA acaba de hacer (o con lo que dijo)."""
    if not episode:
        return ""
    for key in ("result", "said", "goal"):
        value = str(episode.get(key) or "").strip()
        if value:
            return value[:120]
    return ""


def goal_line(goal: Dict[str, Any]) -> str:
    """Lo que ARIA tiene entre manos, y de quién es la idea."""
    text = str(goal.get("goal") or "").strip()
    if not text:
        return ""
    if str(goal.get("origin") or "") == "propia":
        return f"{text} (se lo propone sola)"
    return text


def beat_summary(result: Optional[Dict[str, Any]]) -> str:
    """Qué ha pasado en una vuelta del runtime, en una línea.

    "" cuando no hay nada que contar: ARIA no dice "nada" cada 45 segundos,
    que es como se vuelve ruido. Si ha actuado o ha dicho algo, sale la
    línea; si solo estaba en pausa o sin nada entre manos, calla.
    """
    if not result:
        return ""
    status = str(result.get("status") or "")
    if status in ("idle", "paused"):
        return ""

    episode = result.get("episode") or {}
    said = str(result.get("said") or episode.get("said") or "").strip()
    if said:
        return said

    summary = str(episode.get("result") or "").strip()
    if not summary:
        return ""
    if result.get("ok"):
        return summary
    if "permiso" in summary.lower():
        return summary
    return f"No pude: {summary}"


def lesson_line(status: Optional[Dict[str, Any]]) -> str:
    """Lo que ARIA ha hecho y lo que ha aprendido, en una línea.

    Las lecciones salen de lo que de verdad ha pasado: cada fallo deja una
    regla, y esa regla es lo que ARIA se lleva al siguiente día.
    """
    if not status:
        return ""
    stats = status.get("stats") or {}
    parts: List[str] = []
    actions = int(stats.get("actions") or 0)
    ticks = int(stats.get("ticks") or 0)
    if actions:
        parts.append(f"{actions} acciones")
    if ticks:
        parts.append(f"{ticks} latidos")

    lessons = status.get("lessons") or []
    active = [item for item in lessons if not item.get("suppressed")] if lessons else []
    if active:
        text = str(active[0].get("text") or "").strip()
        if text:
            parts.append(f"lección: {text[:56]}")
    elif lessons:
        parts.append(f"{len(lessons)} lecciones")
    return " · ".join(parts)


def autonomy_mode(status: Optional[Dict[str, Any]]) -> str:
    """El estado del modo autónomo, para la franja."""
    if not status:
        return "?"
    if not status.get("enabled", True):
        return "en pausa"
    return str(status.get("mode") or "activa")
