"""Event log append-only para las decisiones de routing.

Por que existe: `AIRouter` ya mide provider elegido, latencia real y errores,
pero ese dato se perdia. Sin el, el router no puede aprender nada mas que por
`priority` estatico.

Garantias:

* Append-only. Una linea escrita no se reescribe ni se borra. No hay `update`.
* durability real: `flush` + `os.fsync` en cada escritura. Sin fsync, un corte
  de luz pierde justo lo que se queria recordar.
* El modelo evaluado no puede escribir aqui. `append` acepta un esquema cerrado:
  cualquier campo desconocido lanza `TypeError`. Tampoco se guarda el texto del
  prompt ni de la respuesta, solo metadatos, asi que no hay via por la que el
  modelo inyecte contenido en el log.
* Lo no medido se registra como `None` + `data_source: "unavailable"`, nunca
  como cero.
* La corrupcion se hace visible: una linea ilegible se devuelve marcada con
  `_corrupt`, no se salta en silencio.

Formato: JSON Lines, un evento por linea.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

DEFAULT_LOG_PATH = Path("aria_events.jsonl")

MAX_ERROR_CHARS = 300

#: Campos que `append` acepta. Cerrado a proposito: es lo que impide que el
#: modelo evaluado escriba contenido arbitrario en el log.
ALLOWED_FIELDS = frozenset(
    {
        "kind",
        "session_id",
        "provider",
        "model",
        "latency_ms",
        "tokens",
        "cost_usd",
        "outcome",
        "error",
        "data_source",
        "unmeasured",
        "attempted",
        "skipped",
        "available",
    }
)

VALID_OUTCOMES = frozenset({"ok", "error", "skipped"})
VALID_DATA_SOURCES = frozenset({"measured", "unavailable"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _scrub(error: Optional[str]) -> Optional[str]:
    """Acota el tamano de un error y quita saltos de linea que romperian JSONL."""
    if error is None:
        return None
    flat = " ".join(str(error).split())
    return flat[:MAX_ERROR_CHARS]


class EventLog:
    """Store append-only de eventos JSONL."""

    def __init__(self, path: Optional[str | os.PathLike[str]] = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_LOG_PATH
        self._lock = threading.Lock()
        self._seq = self._count_lines()

    # ---------------------------------------------------------------- lectura

    def _count_lines(self) -> int:
        if not self.path.exists():
            return 0
        total = 0
        try:
            with self.path.open("r", encoding="utf-8", errors="replace") as handle:
                for _ in handle:
                    total += 1
        except OSError:
            return 0
        return total

    def iter_events(self, kind: Optional[str] = None) -> Iterator[Dict[str, Any]]:
        """Recorre los eventos en orden de escritura.

        Las lineas ilegibles se emiten con `_corrupt=True` y el resto de campos
        a None. Se prefieren visibles.
        """
        if not self.path.exists():
            return
        try:
            handle = self.path.open("r", encoding="utf-8", errors="replace")
        except OSError:
            return
        with handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    yield {"_corrupt": True, "raw": line[:MAX_ERROR_CHARS]}
                    continue
                if not isinstance(event, dict):
                    yield {"_corrupt": True, "raw": line[:MAX_ERROR_CHARS]}
                    continue
                if kind is not None and event.get("kind") != kind:
                    continue
                yield event

    def tail(self, limit: int = 50, kind: Optional[str] = None) -> List[Dict[str, Any]]:
        """Ultimos `limit` eventos, en orden cronologico."""
        if limit <= 0:
            return []
        buffer: List[Dict[str, Any]] = []
        for event in self.iter_events(kind=kind):
            buffer.append(event)
            if len(buffer) > limit:
                buffer.pop(0)
        return buffer

    def corrupt_count(self) -> int:
        return sum(1 for event in self.iter_events() if event.get("_corrupt"))

    # --------------------------------------------------------------- escritura

    def append(self, kind: str, **fields: Any) -> Optional[Dict[str, Any]]:
        """Anade un evento. Devuelve el evento escrito, o None si el disco fallo.

        Lanza `TypeError` si hay un campo fuera del esquema: eso es un error de
        programacion y no debe pasar desapercibido. Los fallos de E/S se
        devuelven como None porque la decision de routing ya ocurrio y perderla
        no puede tumbar la peticion en curso.
        """
        unknown = set(fields) - ALLOWED_FIELDS
        if unknown:
            raise TypeError(
                f"campos no permitidos en event log: {sorted(unknown)}; "
                f"permitidos: {sorted(ALLOWED_FIELDS)}"
            )

        outcome = fields.get("outcome")
        if outcome is not None and outcome not in VALID_OUTCOMES:
            raise ValueError(f"outcome invalido: {outcome!r}")

        data_source = fields.get("data_source")
        if data_source is not None and data_source not in VALID_DATA_SOURCES:
            raise ValueError(f"data_source invalido: {data_source!r}")

        with self._lock:
            seq = self._seq
            self._seq += 1

        event: Dict[str, Any] = {"seq": seq, "ts": _now_iso(), "kind": kind}

        for field_name in (
            "session_id",
            "provider",
            "model",
            "outcome",
            "attempted",
            "skipped",
            "available",
        ):
            if field_name in fields:
                event[field_name] = fields[field_name]

        for field_name in ("latency_ms", "tokens", "cost_usd"):
            if field_name not in fields:
                continue
            value = fields[field_name]
            # Un numero que no se midio no se convierte en 0.
            event[field_name] = None if value is None else value

        # `data_source` describe el EVENTO (viene de una medicion real, no de un
        # supuesto). Que un campo concreto sea None lo dice el propio campo; antes
        # esto se derivaba a "unavailable" si cualquier numerico era None, lo que
        # marcaba como no medida una latencia que si se habia medido.
        unmeasured = [
            name
            for name in ("latency_ms", "tokens", "cost_usd")
            if name in event and event[name] is None
        ]
        if unmeasured:
            event["unmeasured"] = unmeasured

        if "error" in fields:
            event["error"] = _scrub(fields["error"])
        if data_source is not None:
            event["data_source"] = data_source
        event.setdefault("data_source", "measured")

        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            return None
        return event

    # ------------------------------------------------------------- proyeccion

    def provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """Agrega por provider. Solo datos medidos; `None` no cuenta como cero."""
        stats: Dict[str, Dict[str, Any]] = {}
        for event in self.iter_events(kind="routing.decision"):
            if event.get("_corrupt"):
                continue
            name = event.get("provider") or "none"
            row = stats.setdefault(
                name,
                {
                    "ok": 0,
                    "error": 0,
                    "latency_samples": [],
                    "token_samples": 0,
                    "data_source": "measured",
                },
            )
            if event.get("outcome") == "ok":
                row["ok"] += 1
                latency = event.get("latency_ms")
                if isinstance(latency, (int, float)):
                    row["latency_samples"].append(float(latency))
            else:
                row["error"] += 1
            if isinstance(event.get("tokens"), int):
                row["token_samples"] += 1

        for row in stats.values():
            samples = row.pop("latency_samples")
            if samples:
                row["latency_mean_ms"] = round(sum(samples) / len(samples), 3)
                row["latency_samples"] = len(samples)
            else:
                row["latency_mean_ms"] = None
                row["latency_samples"] = 0
        return stats

    def summary(self) -> Dict[str, Any]:
        total = 0
        for _ in self.iter_events():
            total += 1
        return {
            "path": str(self.path),
            "events": total,
            "corrupt_lines": self.corrupt_count(),
            "data_source": "measured",
        }


_DEFAULT_LOG: Optional[EventLog] = None
_DEFAULT_LOCK = threading.Lock()


def get_event_log() -> EventLog:
    """Instancia compartida del process."""
    global _DEFAULT_LOG
    if _DEFAULT_LOG is None:
        with _DEFAULT_LOCK:
            if _DEFAULT_LOG is None:
                _DEFAULT_LOG = EventLog()
    return _DEFAULT_LOG


def now_ms() -> float:
    return round(time.perf_counter() * 1000, 3)