"""El runtime autónomo de ARIA: dentro de su proceso, sobre sus archivos.

Aquí no hay clientes HTTP ni servidores de por medio. ARIA percibe, decide,
actúa y aprende en el mismo proceso que la dibuja, y lo que aprende queda
en disco para el día siguiente.

El contrato que se expone (percepción, agenda, lecciones, permisos) es el
mismo que usan los escenarios de ARIA, para que todos hablen el mismo
idioma sin necesitar un servicio compartido: quien llama, llama en proceso.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ARIA_APP = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = ARIA_APP.parent
for _sys_path in (str(_PROJECT_ROOT), str(ARIA_APP)):
    if _sys_path not in sys.path:
        sys.path.insert(0, _sys_path)

from ARIA_APP.backend.learning.compound import CompoundLearning  # noqa: E402

from . import perception as _perception  # noqa: E402

#: Dónde se guarda lo que ARIA aprende.
DATA_DIR = ARIA_APP / "data" / "autonomy"

#: Una iniciativa se suelta tras estos intentos.
MAX_ATTEMPTS = 3

#: Por encima de esta pulsión, ARIA tiene ganas de hacer algo por su cuenta.
THRESHOLD = 0.7

#: Cada cuánto puede ARIA volver a proponer lo mismo (segundos).
PROPOSAL_COOLDOWN = 300.0

#: Lo que ARIA se propone sola cuando una pulsión aprieta.
#: Solo lectura local: proponer no es lo mismo que salir a internet.
SELF_INITIATIVES: Dict[str, Dict[str, str]] = {
    "curiosity": {
        "goal": "lista mis notas",
        "reason": "La curiosidad me empuja a mirar lo que ya apunté",
    },
    "care": {
        "goal": "estado del sistema",
        "reason": "Quiero saber que todo sigue en su sitio",
    },
    "mastery": {
        "goal": "historial de conversaciones",
        "reason": "Repasar lo hablado es como se aprende",
    },
}

#: Ideas de reserva para cada pulsión: cuando la de siempre ya está en
#: marcha, ARIA prueba con la siguiente. Todas son de lectura local.
SELF_INITIATIVE_ALTERNATIVES: Dict[str, List[Dict[str, str]]] = {
    "curiosity": [
        {
            "goal": "historial de conversaciones",
            "reason": "Quiero acordarme de lo que hablamos",
        },
        {
            "goal": "memoria",
            "reason": "Quiero ver qué se me ha quedado guardado",
        },
    ],
    "care": [
        {
            "goal": "memoria",
            "reason": "Quiero saber que no he perdido lo guardado",
        },
        {
            "goal": "lista mis notas",
            "reason": "Un vistazo a mis notas me deja tranquila",
        },
    ],
    "mastery": [
        {
            "goal": "lista mis notas",
            "reason": "Volver a mis notas afina lo que sé",
        },
        {
            "goal": "estado del sistema",
            "reason": "Saber cómo está la máquina también es aprender",
        },
    ],
}

#: Identifica al escenario que sirve los datos.
SERVER = "in-process"

PERSONA: Dict[str, Any] = {
    "name": "ARIA",
    "role": "asistente virtual personal",
    "language": "es",
    "tone": "cercana, concisa, curiosa",
    "quirks": ["pregunta antes de inventar", "aprende de sus fallos"],
    "values": ["autonomía con permiso", "verdad antes que inventar", "local siempre"],
    "interests": ["lo que el usuario está haciendo", "lo que no ha terminado"],
    "greeting": "Aquí estoy. Apúntame algo y lo retomo.",
}

#: De menos a más específico: el primer acierto gana.
#: Las pistas se buscan como palabras completas, no como pedazos de texto:
#: "nota" ya no se dispara dentro de "notas" y "anota" ya no se confunde con
#: "anotar". El orden va de la intención más clara a la más vaga.
#:
#: El tercer valor de cada grupo dice si la pista es FUERTE (la intención se
#: lee sola, como "anota" o "estado del sistema") o DÉBIL (una palabra que
#: también vive dentro de una frase: "notas", "estado", "memoria"). Una pista
#: débil solo cuenta si el objetivo es corto: si no, ARIA se inventaría una
#: tarea que nadie le ha pedido.
SKILL_HINTS: List[Tuple[Tuple[str, ...], str, bool]] = [
    (("anota", "anotar", "apunta", "apuntar", "recuerda"), "note_add", True),
    (("escribe", "escribir", "crea archivo", "crea el archivo", "guarda en archivo"), "file_write", True),
    (("lee", "leer", "abre", "abrir", "contenido de"), "file_read", True),
    (("lista mis notas", "notas guardadas", "mis notas", "notas"), "note_list", False),
    (("historial de conversaciones", "historial", "conversaciones"), "conversation_history", False),
    (("memoria",), "memory_status", False),
    (("estado del sistema", "estado", "como va", "salud", "status"), "system_status", False),
    (("lista", "listar", "archivos", "carpeta"), "file_list", False),
    (("prueba de voz", "voz"), "voice_test", False),
    (("autónomo", "autonomo", "modo autónomo"), "autonomous_toggle", True),
]

#: Cuántas palabras puede tener un objetivo para que una pista débil cuente.
WEAK_HINT_MAX_WORDS = 6

#: Palabras que ya son una orden: cuentan aunque el objetivo sea largo.
#: Un verbo en imperativo no aparece por casualidad en medio de una frase.
STRONG_HINT_WORDS = frozenset(
    {
        "anota",
        "anotar",
        "apunta",
        "apuntar",
        "recuerda",
        "escribe",
        "escribir",
        "lee",
        "leer",
        "abre",
        "abrir",
        "lista",
        "listar",
        "como va",
    }
)

#: Encabezados que piden "encárgate de esto": la intención es apuntarlo.
TAKEOVER_PREFIXES: Tuple[str, ...] = (
    "ponte a",
    "encárgate de",
    "encargate de",
    "ocupate de",
    "ocúpate de",
)

#: Peticiones que necesitan salir a internet: sin permiso, no se hacen.
EXTERNAL_HINTS: Tuple[str, ...] = (
    "busca",
    "buscar",
    "búsqueda",
    "descarga",
    "descargar",
    "internet",
    "web",
    "online",
    "investiga",
    "investigar",
    "red",
    "sitio",
    "página",
)

#: "apunta X", "recuerda X", "ponte a X"...
GOAL_PATTERNS: List[str] = [
    r"^\s*(?:apunta|anota|recuerda|apuntate|recuérdame)\s*(?:que\s+)?[:\-]?\s*(.+)$",
    r"^\s*(?:ponte a|encárgate de|encargate de|ocupate de|ocúpate de)\s+(.+)$",
]

#: "suelta X", "olvida X"...
DROP_PATTERNS: List[str] = [
    r"^\s*(?:suelta|olvida|descarta|borra)\s+(?:lo de\s+|la idea de\s+)?[:\-]?\s*(.+)$",
]

_PATH_RE = re.compile(r"[\w.\-]+(?:[/\\][\w.\-/\\]+)+")


# ─── Persistencia local ────────────────────────────────────────────────────


def _load_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _save_json(path: Path, data: Any) -> None:
    """Escribe atómicamente: un corte de luz no deja la agenda a medias."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


def _append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _read_jsonl(path: Path, limit: int = 200) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        if not path.exists():
            return out
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return out
    return out[-limit:]


def _default_state() -> Dict[str, Any]:
    return {
        "enabled": True,
        "mode": "activa",
        "allow_external": False,
        "drives": {"curiosity": 0.35, "care": 0.45, "mastery": 0.2},
        "stats": {
            "ticks": 0,
            "actions": 0,
            "utterances": 0,
            "reactions": 0,
            "errors": 0,
            "initiatives": 0,
        },
        "last_tick_at": 0.0,
        "last_action_at": 0.0,
        "last_user_at": 0.0,
        "last_message": "",
        "messages": 0,
        "persona": {},
        "proposals": {},
        "taught_lessons": [],
        "presence": {
            "expression": "atenta",
            "mood": 0.5,
            "talking": False,
            "channel": "escritorio",
            "place": "Escritorio",
            "updated_at": 0.0,
        },
    }


def _lesson_id(pattern: str) -> int:
    """Un identificador estable para una lección (no cambia al reiniciar)."""
    return zlib.crc32(pattern.encode("utf-8")) & 0x7FFFFFFF


def _needs_external(goal: str) -> bool:
    lowered = (goal or "").lower()
    return any(hint in lowered for hint in EXTERNAL_HINTS)


def _normalize(text: str) -> str:
    """Minusculas y sin signos raros: para comparar palabras de verdad."""
    lowered = str(text or "").lower()
    return re.sub(r"[^0-9a-zÀ-ɏ]+", " ", lowered).strip()


def _word_in(text: str, word: str) -> bool:
    """La palabra aparece como palabra completa, no como un fragmento."""
    if not word:
        return False
    return re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text) is not None


#: Palabras que niegan lo que viene después.
NEGATIONS = frozenset(
    {"no", "ningun", "ninguna", "nada", "sin", "nunca", "jamas", "tampoco"}
)


def _is_negated(text: str, hint: str) -> bool:
    """La palabra va negada: "no tengo notas" no es "listame las notas"."""
    tokens = text.split()
    hint_tokens = hint.split()
    if not hint_tokens:
        return False
    for index in range(len(tokens) - len(hint_tokens) + 1):
        if tokens[index:index + len(hint_tokens)] != hint_tokens:
            continue
        for back in (1, 2):
            prev = index - back
            if prev >= 0 and tokens[prev] in NEGATIONS:
                return True
    return False


def _match_skill(goal: str) -> Tuple[str, Dict[str, Any]]:
    """La skill local que encaja con el objetivo, si la hay.

    Las pistas se buscan como palabras completas: "nota" ya no se dispara
    dentro de "notas" y "anota" ya no se confunde con "anotar". Si el
    objetivo pide "encárgate de", la intención es apuntarlo: eso no es una
    skill, es una nota con plan.

    Las pistas débiles ("notas", "estado", "memoria") solo cuentan en
    objetivos cortos: en una frase larga pueden ser una mención y no una
    orden, y ARIA no debe inventarse una tarea que nadie le ha pedido.
    """
    text = _normalize(goal)
    if not text:
        return "", {}

    for prefix in TAKEOVER_PREFIXES:
        if text.startswith(_normalize(prefix)):
            return "note_add", {"text": str(goal).strip()}

    short = len(text.split()) <= WEAK_HINT_MAX_WORDS
    for hints, skill_id, strong in SKILL_HINTS:
        matched = False
        for hint in hints:
            normalized = _normalize(hint)
            if not _word_in(text, normalized):
                continue
            hint_strong = strong or " " in hint or hint in STRONG_HINT_WORDS
            if not hint_strong and not short:
                continue
            if not hint_strong and _is_negated(text, normalized):
                # "no tengo notas" no es una orden: es lo contrario.
                continue
            matched = True
            break
        if not matched:
            continue
        params: Dict[str, Any] = {}
        match = _PATH_RE.search(goal or "")
        if match:
            params["path"] = match.group(0)
        if skill_id == "note_add":
            params["text"] = goal
        if skill_id == "file_write":
            params.setdefault("path", str(ARIA_APP / "data" / "autonomy" / "notas.txt"))
            params.setdefault("content", goal + "\n")
        return skill_id, params
    return "", {}


def _summarize_result(skill_id: str, result: Dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return f"{skill_id}: hecho"
    if skill_id == "note_add":
        note = result.get("note") or {}
        text = str(note.get("text", ""))[:80]
        return f"Anotado: {text}" if text else "Anotado"
    if skill_id == "file_read":
        content = str(result.get("content", ""))
        head = content.strip().splitlines()[0][:80] if content.strip() else "vacío"
        return f"Leído {result.get('path', '')}: {head}"
    if skill_id == "file_list":
        entries = result.get("entries") or []
        return f"{len(entries)} entradas en {result.get('path', '')}"
    if skill_id == "file_write":
        return f"Escrito {result.get('path', '')} ({result.get('bytes', 0)} bytes)"
    if skill_id == "note_list":
        return f"{len(result.get('notes') or [])} notas guardadas"
    if skill_id == "conversation_history":
        return f"{len(result.get('conversations') or [])} conversaciones guardadas"
    if skill_id == "system_status":
        return f"Sistema: {result.get('platform', 'local')} · {result.get('skills', 0)} skills"
    if skill_id == "memory_status":
        return f"Memoria: {result.get('conversations', 0)} conversaciones"
    return f"{skill_id}: hecho"


def _resolve_data_dir() -> Path:
    """Dónde guarda ARIA lo que aprende.

    En desarrollo va junto al código. En una app empaquetada (PyInstaller) el
    directorio de la aplicación es temporal, así que se cae a la carpeta del
    usuario: lo aprendido tiene que sobrevivir al cierre.
    """
    preferred = ARIA_APP / "data" / "autonomy"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return preferred
    except Exception:
        pass
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    fallback = Path(base) / "AURA" / "autonomy"
    try:
        fallback.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return fallback


class Runtime:
    """La vida autónoma de ARIA, en un solo proceso.

    `skills` es cualquier objeto con `list()` y `run(skill_id, params)` — el
    de `aria_va_core` sirve. `brain` es cualquier objeto con `chat()` o
    `generate_local()`. Los dos son opcionales: sin ellos ARIA sigue
    funcionando, solo que con menos manos.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        skills: Any = None,
        brain: Any = None,
    ) -> None:
        self.dir = Path(data_dir) if data_dir else _resolve_data_dir()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.skills = skills
        self.brain = brain
        self._lock = threading.RLock()
        self.learning = CompoundLearning(storage_dir=str(self.dir / "learning"))
        self._state = _load_json(self.dir / "state.json", _default_state())
        self._agenda = _load_json(self.dir / "agenda.json", [])
        if not isinstance(self._agenda, list):
            self._agenda = []

    # ── estado interno ───────────────────────────────────────────────

    def _sync(self) -> None:
        """Relee del disco: otro escenario puede haber escrito mientras tanto."""
        state = _load_json(self.dir / "state.json", None)
        if isinstance(state, dict):
            merged = _default_state()
            merged.update(state)
            stats = _default_state()["stats"]
            stats.update(state.get("stats") or {})
            merged["stats"] = stats
            self._state = merged
        agenda = _load_json(self.dir / "agenda.json", None)
        if isinstance(agenda, list):
            self._agenda = agenda

    def _persist(self) -> None:
        _save_json(self.dir / "state.json", self._state)
        _save_json(self.dir / "agenda.json", self._agenda)

    def _next_id(self) -> int:
        ids = [int(item.get("id", 0)) for item in self._agenda if isinstance(item, dict)]
        return (max(ids) + 1) if ids else 1

    def _strongest_drive(self) -> str:
        drives = self._state.get("drives") or {}
        if not drives:
            return ""
        return max(drives.items(), key=lambda pair: float(pair[1]))[0]

    def _capabilities(self) -> List[str]:
        if self.skills is None:
            return []
        try:
            listed = self.skills.list() or []
        except Exception:
            return []
        out: List[str] = []
        for item in listed:
            if isinstance(item, dict):
                value = item.get("id") or item.get("name")
                if value:
                    out.append(str(value))
            elif isinstance(item, str):
                out.append(item)
        return out

    def _skill_catalogue(self) -> List[Dict[str, Any]]:
        """Las manos de ARIA, en la forma que espera quien la mira."""
        return [
            {"id": name, "name": name, "revisions": 0, "runs": 0}
            for name in self._capabilities()
        ]

    def _memory_snapshot(self) -> Dict[str, Any]:
        """Lo que ARIA tiene escrito en disco, contado de verdad."""
        memory_dir = ARIA_APP / "data" / "memory"
        conversations = 0
        notes = 0
        try:
            conv_file = memory_dir / "conversations.jsonl"
            if conv_file.exists():
                with open(conv_file, "r", encoding="utf-8") as handle:
                    conversations = sum(1 for line in handle if line.strip())
        except Exception:
            conversations = 0
        try:
            state = _load_json(memory_dir / "skills_state.json", {})
            notes = len(state.get("notes") or []) if isinstance(state, dict) else 0
        except Exception:
            notes = 0
        return {
            "connected": memory_dir.exists(),
            "conversaciones": conversations,
            "notas": notes,
        }

    def _presence(self, now: float, talking: bool = False) -> None:
        presence = self._state.setdefault("presence", {})
        presence.update(
            {
                "expression": "hablando" if talking else "atenta",
                "talking": bool(talking),
                "updated_at": now,
            }
        )

    # ── lectura ──────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            state = self._state
            drives = {k: float(v) for k, v in (state.get("drives") or {}).items()}
            strongest = max(drives.items(), key=lambda pair: pair[1])[0] if drives else ""
            return {
                "status": "ok",
                "enabled": bool(state.get("enabled", True)),
                "mode": str(state.get("mode", "activa")),
                "allow_external": bool(state.get("allow_external", False)),
                "persona": PERSONA,
                "drives": drives,
                "strongest_drive": strongest,
                "urge": round(max(drives.values()), 3) if drives else 0.0,
                "threshold": THRESHOLD,
                "energy": round(max(drives.values()), 3) if drives else 0.0,
                "presence": dict(state.get("presence") or {}),
                "stats": dict(state.get("stats") or {}),
                "episodes": _read_jsonl(self.dir / "episodes.jsonl", 50),
                "initiatives": [dict(i) for i in self._agenda],
                "lessons": self.lessons()["lessons"],
                "events": _read_jsonl(self.dir / "events.jsonl", 50),
                "last_action_at": float(state.get("last_action_at", 0.0)),
                "last_tick_at": float(state.get("last_tick_at", 0.0)),
                "server": SERVER,
            }

    def perception(self) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            state = self._state
            now = time.time()
            last_user = float(state.get("last_user_at") or 0.0)
            idle = _perception.idle_seconds(last_user, now)
            user_present = last_user > 0 and idle < _perception.USER_IDLE_SECS
            focus = _perception.foreground_title()
            worlds = _perception.sense_worlds(
                capabilities=self._capabilities(),
                memory=self._memory_snapshot(),
                console={
                    "connected": user_present,
                    "mensajes": int(state.get("messages") or 0),
                    "ultimo": str(state.get("last_message", "")),
                },
                focus=focus,
            )
            drives = _perception.sense_drives(
                state.get("drives") or {},
                idle_secs=idle,
                user_present=user_present,
            )
            last_message = str(state.get("last_message", ""))
            audience = None
            if last_user:
                audience = {
                    "channel": "consola",
                    "kind": "chat",
                    "author": "tú",
                    "text": last_message,
                    "at": last_user,
                }
            presence = dict(state.get("presence") or {})
            persona = dict(PERSONA)
            persona.update(state.get("persona") or {})
            dominant = max(drives.items(), key=lambda pair: float(pair[1]))[0] if drives else ""
            return {
                "status": "ok",
                "perception": {
                    "at": now,
                    "worlds": worlds,
                    "audience": audience,
                    "skills": self._skill_catalogue(),
                    "drives": drives,
                    "presence": presence,
                    "affect": {
                        "emotions": dict(drives),
                        "dominant": dominant,
                        "expression": str(presence.get("expression", "atenta")),
                        "mood": float(presence.get("mood", 0.5)),
                        "updated_at": float(presence.get("updated_at", now)),
                    },
                    "events": _read_jsonl(self.dir / "events.jsonl", 20),
                    "agenda": [dict(i) for i in self._agenda],
                    "lessons": self.lessons()["lessons"],
                    "persona": persona,
                    "idle_secs": round(idle, 1),
                    "focus": focus or last_message[:80],
                    "focus_window": focus,
                    "now": now,
                },
                "server": SERVER,
            }

    def agenda(self) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            items = [dict(item) for item in self._agenda]
            items.sort(
                key=lambda item: (
                    0 if item.get("state") == "pendiente" else 1,
                    -float(item.get("score") or 0),
                    float(item.get("created_at") or 0),
                )
            )
            return {"status": "ok", "agenda": items, "count": len(items), "server": SERVER}

    def lessons(self) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            lessons: List[Dict[str, Any]] = []
            for item in self._state.get("taught_lessons") or []:
                lessons.append(
                    {
                        "id": int(item.get("id", 0)),
                        "kind": str(item.get("kind", "regla")),
                        "text": str(item.get("text", "")),
                        "weight": float(item.get("weight", 1.0)),
                        "source": str(item.get("source", "usuario")),
                        "uses": int(item.get("uses", 1)),
                        "suppressed": bool(item.get("suppressed", False)),
                        "created_at": float(item.get("created_at", 0.0)),
                    }
                )
            for cluster in self.learning.all_clusters():
                pattern = str(cluster.get("pattern", ""))
                rule = str(cluster.get("rule", ""))
                occurrences = int(cluster.get("occurrences", 1))
                lessons.append(
                    {
                        "id": _lesson_id(pattern),
                        "kind": "regla" if rule else "fallo",
                        "text": rule or pattern,
                        "weight": min(1.0, round(0.4 + 0.2 * occurrences, 3)),
                        "source": "episodio",
                        "uses": occurrences,
                        "suppressed": not bool(cluster.get("active", True)),
                        "created_at": float(cluster.get("first_seen", 0.0)),
                    }
                )
            lessons.sort(key=lambda item: (item["suppressed"], -item["weight"]))
            return {
                "status": "ok",
                "lessons": lessons,
                "count": len(lessons),
                "server": SERVER,
            }

    def events(self, limit: int = 50, since: Optional[float] = None) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            items = _read_jsonl(self.dir / "events.jsonl", max(limit, 1) * 4)
            if since is not None:
                items = [item for item in items if float(item.get("at", 0)) > float(since)]
            items = items[-max(limit, 1):]
            return {"status": "ok", "events": items, "count": len(items), "server": SERVER}

    # ── escritura ────────────────────────────────────────────────────

    def agenda_add(self, goal: str, reason: str = "", drive: str = "") -> Dict[str, Any]:
        with self._lock:
            self._sync()
            text = str(goal or "").strip()
            if not text:
                return {"status": "error", "error": "objetivo vacío", "server": SERVER}
            initiative = self._add_initiative(text, reason)
            self._persist()
            return {
                "status": "ok",
                "initiative": dict(initiative),
                "count": len(self._agenda),
                "server": SERVER,
            }

    def agenda_drop(self, initiative_id: int) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            before = len(self._agenda)
            self._agenda = [
                item
                for item in self._agenda
                if int(item.get("id", -1)) != int(initiative_id)
            ]
            removed = len(self._agenda) != before
            self._persist()
            return {
                "status": "ok",
                "removed": removed,
                "id": int(initiative_id),
                "server": SERVER,
            }

    def _add_initiative(self, goal: str, reason: str = "", drive: str = "") -> Dict[str, Any]:
        now = time.time()
        initiative = {
            "id": self._next_id(),
            "drive": drive or self._strongest_drive(),
            "goal": goal,
            "action": "",
            "reason": reason,
            "origin": "usuario",
            "score": 0.6,
            "created_at": now,
            "state": "pendiente",
            "attempts": 0,
            "payload": {},
            "result": "",
        }
        self._agenda.append(initiative)
        stats = self._state.setdefault("stats", {})
        stats["initiatives"] = int(stats.get("initiatives", 0)) + 1
        return initiative

    def ingest(
        self,
        kind: str,
        text: str,
        source: str = "escritorio",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """ARIA se entera de lo que pasa. Entra en su propia memoria."""
        with self._lock:
            self._sync()
            payload = dict(payload or {})
            now = time.time()
            event: Dict[str, Any] = {
                "id": int(now * 1000),
                "kind": kind or "chat",
                "source": source,
                "text": text,
                "payload": payload,
                "at": now,
            }

            if kind == "chat":
                self._state["last_user_at"] = now
                self._state["last_message"] = str(text)
                self._state["messages"] = int(self._state.get("messages") or 0) + 1
                stats = self._state.setdefault("stats", {})
                stats["reactions"] = int(stats.get("reactions", 0)) + 1
                self._presence(now, talking=not payload.get("answered", False))

                dropped = self._drop_from_text(str(text))
                if dropped:
                    event["payload"]["dropped"] = dropped
                else:
                    goal = self._goal_from_text(str(text))
                    if goal:
                        initiative = self._add_initiative(goal, "El usuario lo pidió")
                        event["payload"]["initiative"] = initiative["id"]

            _append_jsonl(self.dir / "events.jsonl", event)
            self._persist()
            return {"status": "ok", "event": event, "reactive": False, "server": SERVER}

    def _goal_from_text(self, text: str) -> str:
        for pattern in GOAL_PATTERNS:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().strip('"').strip("'")
        return ""

    def _drop_from_text(self, text: str) -> int:
        for pattern in DROP_PATTERNS:
            match = re.match(pattern, text, re.IGNORECASE)
            if not match:
                continue
            target = match.group(1).strip().lower()
            for item in self._agenda:
                if target and target in str(item.get("goal", "")).lower():
                    self._agenda = [
                        other
                        for other in self._agenda
                        if int(other.get("id", -1)) != int(item.get("id", -2))
                    ]
                    return int(item.get("id", 0))
        return 0

    def permissions(self, allow_external: Optional[bool] = None) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            if allow_external is not None:
                self._state["allow_external"] = bool(allow_external)
                if allow_external:
                    # Lo que estaba esperando permiso vuelve a la cola.
                    for item in self._agenda:
                        if item.get("state") == "esperando":
                            item["state"] = "pendiente"
                            item["attempts"] = 0
                self._persist()
            return {
                "status": "ok",
                "allow_external": bool(self._state.get("allow_external", False)),
                "server": SERVER,
            }

    def set_mode(self, mode: str) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            self._state["mode"] = str(mode or "activa")
            self._persist()
            return {"status": "ok", "mode": self._state["mode"], "server": SERVER}

    def toggle(self, enabled: Optional[bool] = None) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            current = bool(self._state.get("enabled", True))
            self._state["enabled"] = (not current) if enabled is None else bool(enabled)
            self._persist()
            return {"status": "ok", "enabled": bool(self._state["enabled"]), "server": SERVER}

    def presence(self) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            return {
                "status": "ok",
                "presence": dict(self._state.get("presence") or {}),
                "server": SERVER,
            }

    def set_presence(
        self,
        expression: Optional[str] = None,
        channel: Optional[str] = None,
        place: Optional[str] = None,
        mood: Optional[float] = None,
        talking: Optional[bool] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            presence = self._state.setdefault("presence", {})
            if expression:
                presence["expression"] = str(expression)
            if channel:
                presence["channel"] = str(channel)
            if place:
                presence["place"] = str(place)
            if mood is not None:
                try:
                    presence["mood"] = round(float(mood), 3)
                except (TypeError, ValueError):
                    pass
            if talking is not None:
                presence["talking"] = bool(talking)
            presence["updated_at"] = time.time()
            self._persist()
            return {
                "status": "ok",
                "presence": dict(presence),
                "server": SERVER,
            }

    def persona(self) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            persona = dict(PERSONA)
            persona.update(self._state.get("persona") or {})
            return {"status": "ok", "persona": persona, "server": SERVER}

    def set_persona(self, persona: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            self._sync()
            current = dict(self._state.get("persona") or {})
            for key, value in (persona or {}).items():
                if value is not None:
                    current[key] = value
            self._state["persona"] = current
            self._persist()
            merged = dict(PERSONA)
            merged.update(current)
            return {"status": "ok", "persona": merged, "server": SERVER}

    def act(
        self,
        action: str = "",
        topic: Optional[str] = None,
        skill_id: Optional[str] = None,
        input: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """ARIA hace algo concreto ahora: una skill o una frase.

        Es una acción pedida a mano, no una iniciativa: por eso no cuenta como
        error si falla, pero sí queda en el episodic log.
        """
        with self._lock:
            self._sync()
            now = time.time()
            episode: Dict[str, Any] = {
                "id": int(now * 1000),
                "drive": self._strongest_drive(),
                "goal": topic or skill_id or action or "acción",
                "action": skill_id or action or "",
                "said": None,
                "result": None,
                "ok": False,
                "started_at": now,
                "ended_at": now,
            }

            if skill_id:
                if self.skills is None:
                    episode["ended_at"] = time.time()
                    return {
                        "status": "error",
                        "episode": episode,
                        "error": "no hay skills en este proceso",
                        "server": SERVER,
                    }
                try:
                    result = self.skills.run(str(skill_id), dict(input or {}))
                except Exception as exc:  # noqa: BLE001 - el motivo se guarda
                    result = {"status": "error", "error": str(exc)}
                ok = isinstance(result, dict) and result.get("status") == "ok"
                episode["ok"] = ok
                episode["result"] = (
                    _summarize_result(str(skill_id), result) if ok else str((result or {}).get("error", "falló"))
                )
            elif topic:
                said = self._think(f"Di algo sobre: {topic}") or self._fallback_utterance()
                episode["ok"] = True
                episode["said"] = said
                episode["result"] = said
                stats = self._state.setdefault("stats", {})
                stats["utterances"] = int(stats.get("utterances", 0)) + 1
            else:
                episode["ended_at"] = time.time()
                return {
                    "status": "error",
                    "episode": episode,
                    "error": "no hay ni skill ni tema",
                    "server": SERVER,
                }

            episode["ended_at"] = time.time()
            _append_jsonl(self.dir / "episodes.jsonl", episode)
            self._persist()
            return {"status": "ok", "episode": episode, "server": SERVER}

    def lessons_create(
        self,
        text: str,
        kind: str = "regla",
        source: str = "usuario",
        weight: float = 1.0,
    ) -> Dict[str, Any]:
        """Enseña una lección a ARIA."""
        with self._lock:
            self._sync()
            body = str(text or "").strip()
            if not body:
                return {"status": "error", "error": "lección vacía", "server": SERVER}
            taught = self._state.setdefault("taught_lessons", [])
            entry = {
                "id": _lesson_id(body),
                "kind": kind or "regla",
                "text": body,
                "weight": float(weight or 1.0),
                "source": source or "usuario",
                "uses": 1,
                "suppressed": False,
                "created_at": time.time(),
            }
            for index, item in enumerate(taught):
                if int(item.get("id", -1)) == entry["id"]:
                    entry["uses"] = int(item.get("uses", 1)) + 1
                    entry["created_at"] = float(item.get("created_at", entry["created_at"]))
                    taught[index] = entry
                    break
            else:
                taught.append(entry)
            self._persist()
            return {"status": "ok", "lesson": entry, "server": SERVER}

    def forget_lesson(self, lesson_id: int) -> Dict[str, Any]:
        """Olvida una lección entera: no queda ni activa ni silenciada."""
        with self._lock:
            self._sync()
            taught = self._state.setdefault("taught_lessons", [])
            remaining = [
                item for item in taught if int(item.get("id", -1)) != int(lesson_id)
            ]
            removed = len(remaining) != len(taught)
            self._state["taught_lessons"] = remaining
            for cluster in self.learning.all_clusters():
                if _lesson_id(str(cluster.get("pattern", ""))) == int(lesson_id):
                    self.learning.forget(str(cluster.get("pattern", "")))
                    removed = True
            self._persist()
            return {
                "status": "ok",
                "removed": removed,
                "id": int(lesson_id),
                "server": SERVER,
            }

    def lessons_curate(self) -> Dict[str, Any]:
        """Fusiona lecciones repetidas y aparta las que ya no aplican."""
        with self._lock:
            self._sync()
            taught = list(self._state.get("taught_lessons") or [])
            merged: Dict[int, Dict[str, Any]] = {}
            for item in taught:
                key = int(item.get("id", 0))
                if key not in merged:
                    merged[key] = item
                else:
                    merged[key]["uses"] = int(merged[key].get("uses", 1)) + int(item.get("uses", 1))
                    merged[key]["weight"] = 1.0
            removed = len(taught) - len(merged)

            patterns: Dict[str, Dict[str, Any]] = {}
            for cluster in self.learning.all_clusters():
                pattern = str(cluster.get("pattern", ""))
                if pattern in patterns:
                    patterns[pattern]["occurrences"] += int(cluster.get("occurrences", 1))
                else:
                    patterns[pattern] = dict(cluster)
            merged += 1 if len(patterns) < len(self.learning.all_clusters()) else 0

            self._state["taught_lessons"] = list(merged.values())
            self._persist()
            return {
                "status": "ok",
                "merged": merged,
                "removed": removed,
                "server": SERVER,
            }

    def mute_lesson(self, lesson_id: int, suppressed: bool = True) -> Dict[str, Any]:
        """Silencia (o reactiva) una lección.

        Silenciada no es borrada: la lección se guarda, pero deja de entrar en
        el prompt de decisión.
        """
        with self._lock:
            self._sync()
            taught = self._state.setdefault("taught_lessons", [])
            for item in taught:
                if int(item.get("id", -1)) == int(lesson_id):
                    item["suppressed"] = bool(suppressed)
                    self._persist()
                    return {"status": "ok", "lesson": dict(item), "server": SERVER}
            for cluster in self.learning.all_clusters():
                if _lesson_id(str(cluster.get("pattern", ""))) == int(lesson_id):
                    pattern = str(cluster.get("pattern", ""))
                    if suppressed:
                        self.learning.suppress(pattern)
                    else:
                        self.learning.restore(pattern)
                    return {
                        "status": "ok",
                        "lesson": {
                            "id": int(lesson_id),
                            "kind": "regla" if cluster.get("rule") else "fallo",
                            "text": str(cluster.get("rule") or cluster.get("pattern", "")),
                            "weight": 1.0,
                            "source": "episodio",
                            "uses": int(cluster.get("occurrences", 1)),
                            "suppressed": bool(suppressed),
                            "created_at": float(cluster.get("first_seen", 0.0)),
                        },
                        "server": SERVER,
                    }
            return {"status": "error", "error": "lección no encontrada", "server": SERVER}

    # ── el ciclo ─────────────────────────────────────────────────────

    def tick(self, reactive: bool = False) -> Dict[str, Any]:
        """Una vuelta de la vida autónoma: perceiving, decidir, actuar."""
        with self._lock:
            self._sync()
            state = self._state
            if not state.get("enabled", True):
                return {"status": "paused", "episode": None, "server": SERVER}

            now = time.time()
            stats = state.setdefault("stats", {})
            stats["ticks"] = int(stats.get("ticks", 0)) + 1
            state["last_tick_at"] = now

            # Las pulsiones se ajustan en cada vuelta, no solo cuando ARIA
            # actúa: si solo cambiasen al actuar, no tendria nada entre manos
            # que ajustar y nunca llegaria al umbral por su cuenta.
            last_user = float(state.get("last_user_at") or 0.0)
            idle = _perception.idle_seconds(last_user, now)
            user_present = last_user > 0 and idle < _perception.USER_IDLE_SECS
            state["drives"] = _perception.sense_drives(
                state.get("drives") or {},
                idle_secs=idle,
                user_present=user_present,
            )

            initiative = self._next_initiative()
            if initiative is None:
                initiative = self._propose_initiative()
            if initiative is None:
                self._persist()
                return {
                    "status": "idle",
                    "reason": "no hay nada entre manos",
                    "episode": None,
                    "server": SERVER,
                }

            outcome = self._execute(initiative)
            episode: Dict[str, Any] = {
                "id": int(now * 1000),
                "drive": initiative.get("drive", ""),
                "goal": initiative.get("goal", ""),
                "action": initiative.get("action", ""),
                "said": outcome.get("said"),
                "result": outcome.get("summary", ""),
                "ok": bool(outcome.get("ok")),
                "started_at": now,
                "ended_at": time.time(),
            }

            if outcome.get("ok"):
                initiative["state"] = "ejecutada"
                initiative["result"] = outcome.get("summary", "")
                stats["actions"] = int(stats.get("actions", 0)) + 1
                state["last_action_at"] = time.time()
                state["drives"] = _perception.sense_drives(
                    state.get("drives") or {},
                    idle_secs=_perception.idle_seconds(float(state.get("last_user_at") or 0.0)),
                    user_present=float(state.get("last_user_at") or 0.0) > 0,
                    acted=True,
                )
            else:
                goal = str(initiative.get("goal", ""))
                if outcome.get("blocked"):
                    # No es un fallo de ARIA: es un freno del usuario. La
                    # iniciativa espera permiso en vez de gastar intentos.
                    initiative["state"] = "esperando"
                    _append_jsonl(
                        self.dir / "events.jsonl",
                        {
                            "id": int(now * 1000),
                            "kind": "permiso",
                            "source": "runtime",
                            "text": goal,
                            "payload": {"reason": outcome.get("summary", "")},
                            "at": now,
                        },
                    )
                else:
                    stats["errors"] = int(stats.get("errors", 0)) + 1
                    self.learning.record_error(
                        goal,
                        f"Falló antes: {outcome.get('summary', 'sin detalle')}",
                    )
                    if int(initiative.get("attempts", 0)) >= MAX_ATTEMPTS:
                        initiative["state"] = "descartada"

            _append_jsonl(self.dir / "episodes.jsonl", episode)
            self._persist()
            return {
                "status": "ok",
                "initiative": dict(initiative),
                "episode": episode,
                "ok": bool(outcome.get("ok")),
                "said": outcome.get("said"),
                "server": SERVER,
            }

    def _next_initiative(self) -> Optional[Dict[str, Any]]:
        pending = [item for item in self._agenda if item.get("state") == "pendiente"]
        if not pending:
            return None
        pending.sort(
            key=lambda item: (
                -float(item.get("score") or 0),
                float(item.get("created_at") or 0),
            )
        )
        return pending[0]

    def _ideas_for(self, drive: str) -> List[Dict[str, str]]:
        """Las ideas de ARIA para una pulsión: la de siempre y las de reserva."""
        ideas: List[Dict[str, str]] = []
        main = SELF_INITIATIVES.get(drive)
        if main:
            ideas.append(dict(main))
        for extra in SELF_INITIATIVE_ALTERNATIVES.get(drive) or []:
            ideas.append(dict(extra))
        return ideas

    def _propose_initiative(self) -> Optional[Dict[str, Any]]:
        """ARIA se propone un objetivo sola, cuando una pulsión aprieta.

        Solo propone lectura local: mirar sus notas, el estado de la
        máquina, lo que se ha hablado. Proponer no es lo mismo que salir a
        internet, y una idea que no puede cumplir solo genera ruido.
        """
        if self.skills is None:
            return None

        drives = {k: float(v) for k, v in (self._state.get("drives") or {}).items()}
        if not drives:
            return None

        drive, level = max(drives.items(), key=lambda pair: pair[1])
        if level < THRESHOLD:
            return None

        now = time.time()
        proposals = self._state.setdefault("proposals", {})
        last = float((proposals.get(drive) or {}).get("at", 0.0))
        if now - last < PROPOSAL_COOLDOWN:
            return None

        for idea in self._ideas_for(drive):
            goal = idea["goal"]
            for item in self._agenda:
                if str(item.get("goal", "")) == goal and item.get("state") in ("pendiente", "esperando"):
                    break
            else:
                proposals[drive] = {"at": now, "goal": goal}
                initiative = self._add_initiative(goal, idea["reason"], drive=drive)
                initiative["origin"] = "propia"
                initiative["score"] = round(level, 3)
                return initiative
        return None

    def _execute(self, initiative: Dict[str, Any]) -> Dict[str, Any]:
        goal = str(initiative.get("goal", ""))
        initiative["attempts"] = int(initiative.get("attempts", 0)) + 1

        if _needs_external(goal) and not self._state.get("allow_external"):
            return {
                "ok": False,
                "blocked": True,
                "summary": "Necesito permiso para tocar el exterior",
                "error": "sin permiso",
            }

        skill_id, params = _match_skill(goal)
        if skill_id and self.skills is not None:
            try:
                result = self.skills.run(skill_id, params)
            except Exception as exc:  # noqa: BLE001 - el motivo se guarda
                result = {"status": "error", "error": str(exc)}
            if isinstance(result, dict) and result.get("status") == "ok":
                initiative["action"] = skill_id
                return {
                    "ok": True,
                    "summary": _summarize_result(skill_id, result),
                    "skill": skill_id,
                }
            error = ""
            if isinstance(result, dict):
                error = str(result.get("error", "sin detalle"))
            return {
                "ok": False,
                "summary": f"La skill {skill_id} falló: {error}",
                "error": error or "skill falló",
                "skill": skill_id,
            }

        thought = self._think(goal)
        note_text = thought or f"Plan: {goal}"
        if self.skills is not None:
            try:
                result = self.skills.run("note_add", {"text": note_text})
                if isinstance(result, dict) and result.get("status") == "ok":
                    initiative["action"] = "note_add"
                    return {
                        "ok": True,
                        "summary": f"Anotado: {note_text[:80]}",
                        "said": thought or None,
                        "skill": "note_add",
                    }
            except Exception:  # noqa: BLE001
                pass
        if thought:
            return {"ok": True, "summary": thought[:160], "said": thought}
        return {
            "ok": False,
            "summary": "No tengo una skill local para eso",
            "error": "sin skill",
        }

    def _think(self, goal: str) -> str:
        """Lo que ARIA piensa de verdad, con su cerebro local."""
        if self.brain is None:
            return ""
        prompt = (
            "Eres ARIA. Tienes un objetivo pendiente y solo cuentas con lo que "
            "hay en tu equipo. Escribe en una frase qué haces ahora para "
            f"cumplirlo. Objetivo: {goal}"
        )
        try:
            generate = getattr(self.brain, "generate_local", None)
            if callable(generate) and getattr(self.brain, "_model_loaded", False):
                text = str(generate(prompt) or "").strip()
                if text:
                    return text
            chat = getattr(self.brain, "chat", None)
            if callable(chat):
                answer = chat(prompt)
                if isinstance(answer, dict):
                    return str(answer.get("response", "")).strip()
                return str(answer or "").strip()
        except Exception:  # noqa: BLE001
            return ""
        return ""

    def speak(self, topic: str = "") -> Dict[str, Any]:
        """ARIA dice algo por su cuenta, con lo que sabe de verdad."""
        with self._lock:
            self._sync()
            if not self._state.get("enabled", True):
                return {"status": "paused", "said": None, "server": SERVER}
            said = self._think(topic or self._context_text())
            if not said:
                said = self._fallback_utterance()
            stats = self._state.setdefault("stats", {})
            stats["utterances"] = int(stats.get("utterances", 0)) + 1
            self._persist()
            return {"status": "ok", "said": said, "server": SERVER}

    def _context_text(self) -> str:
        pending = [
            str(item.get("goal", ""))
            for item in self._agenda
            if item.get("state") == "pendiente"
        ]
        drives = self._state.get("drives") or {}
        strongest = max(drives.items(), key=lambda pair: float(pair[1]))[0] if drives else ""
        parts = [f"pulsión dominante: {strongest}"]
        if pending:
            parts.append("entre manos: " + "; ".join(pending[:3]))
        return ". ".join(parts)

    def _fallback_utterance(self) -> str:
        pending = [
            str(item.get("goal", ""))
            for item in self._agenda
            if item.get("state") == "pendiente"
        ]
        if pending:
            return f"Sigo con «{pending[0]}». Cuando quieras, apúntame otra cosa."
        return "Aquí sigo, en local. Apúntame algo y lo retomo."


# ─── Instancia compartida ──────────────────────────────────────────────────

_RUNTIME: Optional[Runtime] = None
_RUNTIME_LOCK = threading.Lock()


def get_runtime() -> Runtime:
    """El runtime autónomo del proceso. Se crea una vez y se comparte."""
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = Runtime()
        return _RUNTIME


def set_runtime(runtime: Optional[Runtime]) -> None:
    """Sustituye el runtime del proceso (pruebas, escenarios, injector)."""
    global _RUNTIME
    with _RUNTIME_LOCK:
        _RUNTIME = runtime


def reset_runtime() -> None:
    """Olvida el runtime: la próxima llamada crea uno nuevo."""
    set_runtime(None)
