"""BLOQUE 87 - Behavioral Anomaly Detector + Quarantine Controller (parte 1/3)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

# Umbrales de detección local (ajustables, sin red, sin cloud).
MAX_EVENT_RATE = 120          # eventos por ventana
WINDOW_S = 10.0
MAX_FAILED_LOGINS = 5
MAX_FILE_DELETES = 20
MAX_NETWORK_CONNECTIONS = 60
SUSPICIOUS_PATTERNS = (
    re.compile(r"rm\s+-rf", re.IGNORECASE),
    re.compile(r"curl\s+.*\|\s*(?:sh|bash|python)", re.IGNORECASE),
    re.compile(r"wget\s+.*\|\s*sh", re.IGNORECASE),
    re.compile(r"chmod\s+\+x\s+/", re.IGNORECASE),
    re.compile(r"(?:base64\s+-d|eval\s*\()", re.IGNORECASE),
    re.compile(r"(?:/etc/passwd|/etc/shadow)", re.IGNORECASE),
    re.compile(r"(?:netcat|nc\s+-[el])", re.IGNORECASE),
)
QUARANTINE_DIR = "backend/security_state/quarantine"
ALERT_LOG = "backend/security_state/alerts.jsonl"


def _now() -> float:
    return time.time()


def _safe_id(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _ensure_dir(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = Path.cwd() / p
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class SecurityEvent:
    event_id: str = ""
    category: str = ""          # process | network | file | auth | memory
    severity: str = "low"       # low | medium | high | critical
    signal: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)
    ts: float = 0.0
    source: str = "local"

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = uuid.uuid4().hex[:12]
        if not self.ts:
            self.ts = _now()

    def to_dict(self) -> Dict[str, Any]:
        return {"event_id": self.event_id, "category": self.category,
                "severity": self.severity, "signal": self.signal,
                "detail": self.detail, "ts": self.ts, "source": self.source,
                "offline_only": True}


@dataclass
class ThreatAlert:
    alert_id: str = ""
    rule_id: str = ""
    severity: str = "medium"
    title: str = ""
    evidence: str = ""
    events: List[str] = field(default_factory=list)
    ts: float = 0.0
    status: str = "open"        # open | mitigated | quarantined | false_positive
    action: str = ""            # none | quarantine | suspend | block
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.alert_id:
            self.alert_id = uuid.uuid4().hex[:12]
        if not self.ts:
            self.ts = _now()

    def to_dict(self) -> Dict[str, Any]:
        return {"alert_id": self.alert_id, "rule_id": self.rule_id,
                "severity": self.severity, "title": self.title,
                "evidence": self.evidence, "events": list(self.events),
                "ts": self.ts, "status": self.status, "action": self.action,
                "offline_only": self.offline_only}


@dataclass
class QuarantineRecord:
    record_id: str = ""
    target: str = ""
    reason: str = ""
    alert_id: str = ""
    mode: str = "file"          # file | process | network
    ts: float = 0.0
    restored: bool = False
    offline_only: bool = True

    def __post_init__(self) -> None:
        if not self.record_id:
            self.record_id = uuid.uuid4().hex[:12]
        if not self.ts:
            self.ts = _now()

    def to_dict(self) -> Dict[str, Any]:
        return {"record_id": self.record_id, "target": self.target,
                "reason": self.reason, "alert_id": self.alert_id,
                "mode": self.mode, "ts": self.ts, "restored": self.restored,
                "offline_only": self.offline_only}


class BehavioralAnomalyDetector:
    """Detector local de anomalías comportamentales (100% offline)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: List[SecurityEvent] = []
        self._rate: Dict[str, List[float]] = {}
        self._failed_logins: int = 0
        self._file_deletes: int = 0
        self._connections: int = 0
        self._baseline: Dict[str, Any] = {}

    def feed(self, category: str, signal: str, severity: str = "low",
             detail: Optional[Dict[str, Any]] = None) -> SecurityEvent:
        ev = SecurityEvent(category=category, signal=signal, severity=severity,
                           detail=detail or {})
        with self._lock:
            self._events.append(ev)
            self._events = self._events[-5000:]
            self._rate.setdefault(category, []).append(ev.ts)
            self._rate[category] = [t for t in self._rate[category]
                                    if t > _now() - WINDOW_S]
            if category == "auth" and signal == "login_failed":
                self._failed_logins += 1
            if category == "file" and signal in ("delete", "bulk_delete"):
                self._file_deletes += 1
            if category == "network" and signal == "new_connection":
                self._connections += 1
        return ev

    def scan_text(self, text: str, category: str = "process") -> List[SecurityEvent]:
        """Escanea texto (comandos, scripts, args) en busca de patrones sospechosos."""
        found: List[SecurityEvent] = []
        for pat in SUSPICIOUS_PATTERNS:
            m = pat.search(text or "")
            if m:
                found.append(self.feed(category, "suspicious_pattern",
                                       severity="high",
                                       detail={"match": m.group(0)[:200],
                                               "text_len": len(text or "")}))
        return found

    def anomalies(self) -> List[SecurityEvent]:
        """Devuelve anomalías detectadas en la última ventana."""
        out: List[SecurityEvent] = []
        now = _now()
        with self._lock:
            for cat, stamps in self._rate.items():
                rate = len(stamps)
                if cat == "auth" and self._failed_logins >= MAX_FAILED_LOGINS:
                    out.append(SecurityEvent(category=cat, signal="brute_force",
                                             severity="critical",
                                             detail={"failed_logins": self._failed_logins,
                                                     "window_s": WINDOW_S}))
                if cat == "file" and self._file_deletes >= MAX_FILE_DELETES:
                    out.append(SecurityEvent(category=cat, signal="mass_deletion",
                                             severity="critical",
                                             detail={"deletes": self._file_deletes}))
                if cat == "network" and self._connections >= MAX_NETWORK_CONNECTIONS:
                    out.append(SecurityEvent(category=cat, signal="connection_flood",
                                             severity="high",
                                             detail={"connections": self._connections,
                                                     "rate": rate}))
                if rate > MAX_EVENT_RATE:
                    out.append(SecurityEvent(category=cat, signal="event_flood",
                                             severity="high",
                                             detail={"rate": rate, "window_s": WINDOW_S}))
            recent = [e for e in self._events if e.ts > now - WINDOW_S]
        return out + [e for e in recent if e.severity in ("high", "critical")]

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {"events": len(self._events),
                    "rate": {k: len(v) for k, v in self._rate.items()},
                    "failed_logins": self._failed_logins,
                    "file_deletes": self._file_deletes,
                    "connections": self._connections}

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._rate.clear()
            self._failed_logins = 0
            self._file_deletes = 0
            self._connections = 0


class DefenseEngine:
    """Motor local de mitigación de amenazas, cuarentena y rollback (100% offline)."""

    def __init__(self, detector: Optional[BehavioralAnomalyDetector] = None) -> None:
        self._lock = threading.Lock()
        self.detector = detector or BehavioralAnomalyDetector()
        self._alerts: Dict[str, ThreatAlert] = {}
        self._quarantine: Dict[str, QuarantineRecord] = {}
        self._watchers: List[Callable[[Dict[str, Any]], None]] = []
        self._qdir = _ensure_dir(QUARANTINE_DIR)
        self._alog = _ensure_dir(os.path.dirname(ALERT_LOG))
        self._rules: List[Dict[str, Any]] = []
        self._load_rules()

    def _load_rules(self) -> None:
        default = [
            {"rule_id": "brute_force", "signal": "brute_force", "action": "suspend",
             "severity": "critical", "title": "Posible fuerza bruta de login"},
            {"rule_id": "mass_deletion", "signal": "mass_deletion", "action": "quarantine",
             "severity": "critical", "title": "Borrado masivo de archivos detectado"},
            {"rule_id": "connection_flood", "signal": "connection_flood", "action": "block",
             "severity": "high", "title": "Inundación de conexiones de red"},
            {"rule_id": "event_flood", "signal": "event_flood", "action": "suspend",
             "severity": "high", "title": "Flujo de eventos anómalo"},
            {"rule_id": "suspicious_pattern", "signal": "suspicious_pattern",
             "action": "quarantine", "severity": "high",
             "title": "Patrón de comando sospechoso detectado"},
        ]
        with self._lock:
            self._rules = default

    def on_alert(self, cb: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            self._watchers.append(cb)

    def _emit(self, evt: Dict[str, Any]) -> None:
        with self._lock:
            cbs = list(self._watchers)
        for cb in cbs:
            try:
                cb(evt)
            except Exception:
                pass

    def _append_alert_log(self, alert: ThreatAlert) -> None:
        try:
            line = json.dumps(alert.to_dict(), ensure_ascii=False)
            with open(self._alog / ALERT_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def evaluate(self, events: Optional[List[SecurityEvent]] = None) -> List[ThreatAlert]:
        """Corre las reglas contra anomalías y aplica acciones defensivas."""
        pool = events if events is not None else self.detector.anomalies()
        new_alerts: List[ThreatAlert] = []
        with self._lock:
            rules = list(self._rules)
        for ev in pool:
            for rule in rules:
                if rule["signal"] != ev.signal:
                    continue
                alert = ThreatAlert(rule_id=rule["rule_id"], severity=rule["severity"],
                                    title=rule["title"],
                                    evidence=ev.signal,
                                    events=[ev.event_id],
                                    action=rule["action"])
                self._apply_action(alert)
                with self._lock:
                    self._alerts[alert.alert_id] = alert
                self._append_alert_log(alert)
                self._emit({"type": "alert", **alert.to_dict()})
                new_alerts.append(alert)
        return new_alerts

    def _apply_action(self, alert: ThreatAlert) -> None:
        action = alert.action
        target = alert.evidence
        if action == "none":
            alert.status = "mitigated"
            return
        rec = QuarantineRecord(target=target, reason=alert.title,
                               alert_id=alert.alert_id, mode="file")
        try:
            if action in ("quarantine", "block"):
                dest = self._qdir / f"{rec.record_id}_{_safe_id(target)}"
                src = Path(target)
                if src.exists() and src.is_file():
                    src.replace(dest)
                    rec.mode = "file"
                alert.status = "quarantined"
            elif action == "suspend":
                alert.status = "quarantined"
            rec.mode = "process"
        except Exception:
            alert.status = "false_positive"
            return
        with self._lock:
            self._quarantine[rec.record_id] = rec
        self._emit({"type": "quarantined", **rec.to_dict()})

    def restore(self, record_id: str) -> Dict[str, Any]:
        with self._lock:
            rec = self._quarantine.get(record_id)
        if rec is None:
            return {"restored": False, "reason": "not found"}
        try:
            dest = self._qdir / f"{rec.record_id}_{_safe_id(rec.target)}"
            if dest.exists():
                dest.replace(Path(rec.target))
            rec.restored = True
            with self._lock:
                if rec.alert_id in self._alerts:
                    self._alerts[rec.alert_id].status = "mitigated"
            self._emit({"type": "restored", **rec.to_dict()})
            return {"restored": True, **rec.to_dict()}
        except Exception as exc:
            return {"restored": False, "reason": str(exc)[:200], "offline_only": True}

    def alerts(self, status: Optional[str] = None, limit: int = 100) -> List[ThreatAlert]:
        with self._lock:
            items = list(self._alerts.values())
        if status:
            items = [a for a in items if a.status == status]
        return items[-limit:]

    def quarantine(self, limit: int = 100) -> List[QuarantineRecord]:
        with self._lock:
            return list(self._quarantine.values())[-limit:]

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {"online": True, "runner": "local",
                    "events": len(self.detector._events),
                    "alerts": len(self._alerts),
                    "quarantined": len(self._quarantine),
                    "rules": len(self._rules),
                    "offline_only": True}

    def reset(self) -> None:
        with self._lock:
            self._alerts.clear()
            self._quarantine.clear()
        self.detector.reset()


_global_def: Optional[DefenseEngine] = None
_def_lock = threading.Lock()


def get_defense_engine() -> DefenseEngine:
    global _global_def
    with _def_lock:
        if _global_def is None:
            _global_def = DefenseEngine()
        return _global_def


def reset_defense_engine() -> None:
    global _global_def
    with _def_lock:
        _global_def = None


__all__ = [
    "BehavioralAnomalyDetector",
    "DefenseEngine",
    "QuarantineRecord",
    "SecurityEvent",
    "ThreatAlert",
    "get_defense_engine",
    "reset_defense_engine",
]