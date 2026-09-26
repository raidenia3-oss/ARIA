"""Monitoring manager for AURA observability."""

from __future__ import annotations

import datetime
import os
import platform
import shutil
import time
from typing import Any, Dict, List, Optional

from backend.database import SessionLocal
from backend.models import MetricSnapshot


class SystemMonitor:
    """Recolecta métricas locales de CPU, RAM, disco y proceso."""

    def __init__(self) -> None:
        self.start_time = time.time()
        self.samples: List[Dict[str, Any]] = []

    def snapshot(self) -> Dict[str, Any]:
        cpu = self._cpu_usage()
        ram = self._ram_usage()
        disk = self._disk_usage()
        proc = self._process_usage()
        now = time.time()
        uptime_seconds = now - self.start_time

        snapshot = {
            "timestamp": now,
            "datetime": datetime.datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": round(uptime_seconds, 2),
            "cpu": cpu,
            "ram": ram,
            "disk": disk,
            "process": proc,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        }

        self.samples.append(snapshot)
        if len(self.samples) > 200:
            self.samples = self.samples[-200:]
        return snapshot

    def latest(self) -> Dict[str, Any]:
        if not self.samples:
            return self.snapshot()
        return self.samples[-1]

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.samples[-limit:]

    def _cpu_usage(self) -> Dict[str, Any]:
        try:
            if hasattr(os, "getloadavg"):
                load = os.getloadavg()[0]
                cores = os.cpu_count() or 1
                return {"load1": round(load, 2), "cores": cores, "usage_percent": round(min(load / cores * 100, 100), 1)}
            return {"load1": 0.0, "cores": os.cpu_count() or 1, "usage_percent": 0.0}
        except Exception:
            return {"load1": 0.0, "cores": 1, "usage_percent": 0.0}

    def _ram_usage(self) -> Dict[str, Any]:
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "total_mb": round(mem.total / (1024 * 1024), 1),
                "used_mb": round(mem.used / (1024 * 1024), 1),
                "available_mb": round(mem.available / (1024 * 1024), 1),
                "percent": round(mem.percent, 1),
            }
        except Exception:
            try:
                import resource
                usage = resource.getrusage(resource.RUSAGE_SELF)
                return {
                    "total_mb": 0.0,
                    "used_mb": round(usage.ru_maxrss / 1024, 1),
                    "available_mb": None,
                    "percent": 0.0,
                }
            except Exception:
                return {"total_mb": 0.0, "used_mb": 0.0, "available_mb": 0.0, "percent": 0.0}

    def _disk_usage(self) -> Dict[str, Any]:
        try:
            usage = shutil.disk_usage(os.getcwd())
            return {
                "total_mb": round(usage.total / (1024 * 1024), 1),
                "used_mb": round(usage.used / (1024 * 1024), 1),
                "free_mb": round(usage.free / (1024 * 1024), 1),
                "percent": round(usage.used / usage.total * 100, 1),
            }
        except Exception:
            return {"total_mb": 0.0, "used_mb": 0.0, "free_mb": 0.0, "percent": 0.0}

    def _process_usage(self) -> Dict[str, Any]:
        try:
            import psutil
            proc = psutil.Process()
            with proc.oneshot():
                return {
                    "pid": proc.pid,
                    "cpu_percent": round(proc.cpu_percent(interval=0.0), 1),
                    "memory_mb": round(proc.memory_info().rss / (1024 * 1024), 1),
                    "threads": proc.num_threads(),
                }
        except Exception:
            return {"pid": os.getpid(), "cpu_percent": 0.0, "memory_mb": 0.0, "threads": 1}


class AlertManager:
    """Evalúa umbrales y genera alertas simples."""

    def __init__(self) -> None:
        self.alerts: List[Dict[str, Any]] = []

    def evaluate(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        alerts: List[Dict[str, Any]] = []
        cpu = snapshot.get("cpu", {}).get("usage_percent", 0)
        ram = snapshot.get("ram", {}).get("percent", 0)
        disk = snapshot.get("disk", {}).get("percent", 0)

        if cpu >= 90:
            alerts.append({"severity": "critical", "metric": "cpu", "message": f"CPU usage high: {cpu}%", "value": cpu})
        elif cpu >= 75:
            alerts.append({"severity": "warning", "metric": "cpu", "message": f"CPU usage elevated: {cpu}%", "value": cpu})

        if ram >= 90:
            alerts.append({"severity": "critical", "metric": "ram", "message": f"RAM usage high: {ram}%", "value": ram})
        elif ram >= 75:
            alerts.append({"severity": "warning", "metric": "ram", "message": f"RAM usage elevated: {ram}%", "value": ram})

        if disk >= 95:
            alerts.append({"severity": "critical", "metric": "disk", "message": f"Disk usage high: {disk}%", "value": disk})
        elif disk >= 85:
            alerts.append({"severity": "warning", "metric": "disk", "message": f"Disk usage elevated: {disk}%", "value": disk})

        self.alerts = alerts
        return alerts

    def latest_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self.alerts[-limit:]


class MonitoringManager:
    """Gestor central de monitoreo."""

    def __init__(self) -> None:
        self.monitor = SystemMonitor()
        self.alerts = AlertManager()

    def collect(self) -> Dict[str, Any]:
        snapshot = self.monitor.snapshot()
        alert_list = self.alerts.evaluate(snapshot)
        return {
            "snapshot": snapshot,
            "alerts": alert_list,
            "alert_count": len(alert_list),
        }

    def get_status(self) -> Dict[str, Any]:
        snapshot = self.monitor.latest()
        alert_list = self.alerts.latest_alerts()
        alert_count = len(alert_list)
        status = "healthy"
        if any(a["severity"] == "critical" for a in alert_list):
            status = "critical"
        elif any(a["severity"] == "warning" for a in alert_list):
            status = "warning"

        return {
            "status": status,
            "cpu_percent": snapshot.get("cpu", {}).get("usage_percent", 0),
            "ram_percent": snapshot.get("ram", {}).get("percent", 0),
            "disk_percent": snapshot.get("disk", {}).get("percent", 0),
            "alert_count": alert_count,
            "latest_alerts": alert_list,
        }

    def get_metrics(self, limit: int = 50) -> Dict[str, Any]:
        history = self.monitor.history(limit=limit)
        return {
            "count": len(history),
            "metrics": history,
        }

    def get_alerts(self, limit: int = 20) -> Dict[str, Any]:
        alert_list = self.alerts.latest_alerts(limit=limit)
        return {
            "count": len(alert_list),
            "alerts": alert_list,
        }

    def save_snapshot(self, period: str = "1h") -> None:
        snapshot = self.monitor.latest()
        db = SessionLocal()
        try:
            row = MetricSnapshot(
                period=period,
                metrics=str(snapshot),
                created_at=time.time(),
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
