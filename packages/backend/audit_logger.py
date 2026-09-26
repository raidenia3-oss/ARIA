"""Audit logger for AURA compliance and administrative traceability."""

from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AuditEventType(str, Enum):
    ADMIN_ACTION = "admin_action"
    SECURITY_EVENT = "security_event"
    DATA_ACCESS = "data_access"
    DEPLOYMENT = "deployment"
    COMPLIANCE = "compliance"
    HEALTH_CHECK = "health_check"
    SYSTEM = "system"


@dataclass
class AuditEvent:
    event_id: str
    event_type: AuditEventType
    actor: str
    action: str
    resource: str
    result: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class AuditLogger:
    """Registro de auditoría empresarial."""

    def __init__(self, export_dir: str = "/tmp/aura_audit") -> None:
        self.export_dir = export_dir
        self.events: List[AuditEvent] = []
        os.makedirs(export_dir, exist_ok=True)

    def log(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        if len(self.events) > 1000:
            self.events = self.events[-1000:]
        return event

    def history(self, limit: int = 100) -> List[AuditEvent]:
        return self.events[-limit:]

    def export_events(self, event_type: Optional[AuditEventType] = None) -> str:
        filtered = self.events
        if event_type:
            filtered = [e for e in self.events if e.event_type == event_type]
        path = os.path.join(self.export_dir, f"audit-{int(time.time())}.json")
        payload = [e.__dict__ for e in filtered]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return path

    def export_csv(self, event_type: Optional[AuditEventType] = None) -> str:
        filtered = self.events
        if event_type:
            filtered = [e for e in self.events if e.event_type == event_type]
        path = os.path.join(self.export_dir, f"audit-{int(time.time())}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["event_id", "event_type", "actor", "action", "resource", "result", "created_at"])
            writer.writeheader()
            for e in filtered:
                row = e.__dict__.copy()
                row["event_type"] = row["event_type"].value if hasattr(row["event_type"], "value") else str(row["event_type"])
                writer.writerow({k: row.get(k, "") for k in writer.fieldnames})
        return path
