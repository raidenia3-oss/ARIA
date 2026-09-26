"""
Alertas básicas para AURA.

Revisa condiciones y guarda alertas en logs/alerts.jsonl.
Opcional: envía a Discord/Telegram si hay token configurado.

Uso:
    python training/scripts/alerts.py
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("alerts")

ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = ROOT / "logs"
ALERTS_FILE = LOGS_DIR / "alerts.jsonl"
INTERACTIONS_FILE = ROOT / "training" / "data" / "interactions.jsonl"
FEEDBACK_FILE = ROOT / "training" / "data" / "feedback.jsonl"
BACKUP_DIR = ROOT / "fine-tuned-ame" / "backups"
HEALTH_FILE = ROOT / "logs" / "health.jsonl"


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def save_alert(alert: Dict[str, Any]) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(ALERTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(alert, ensure_ascii=False) + "\n")


def send_external(alert: Dict[str, Any]) -> None:
    webhook = os.getenv("ALERT_DISCORD_WEBHOOK")
    if webhook:
        try:
            import urllib.request
            payload = json.dumps({"content": f"AURA ALERT: {alert['message']}"}).encode()
            req = urllib.request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass


def check_error_rate(metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    alerts = []
    if not metrics:
        return alerts
    recent = metrics[-100:]
    total = sum(1 for r in recent if r.get("type") == "request_end")
    errors = sum(1 for r in recent if r.get("type") == "request_end" and r.get("status_code", 200) >= 400)
    if total >= 10 and (errors / total) > 0.2:
        alerts.append({
            "ts": datetime.now().isoformat(),
            "type": "error_rate",
            "message": f"Error rate {errors/total:.1%} en últimos {total} requests",
        })
    return alerts


def check_backup_age() -> List[Dict[str, Any]]:
    alerts = []
    if not BACKUP_DIR.exists():
        return alerts
    backups = sorted([d for d in BACKUP_DIR.iterdir() if d.is_dir()])
    if not backups:
        alerts.append({
            "ts": datetime.now().isoformat(),
            "type": "backup_age",
            "message": "Sin backups locales de LoRA",
        })
        return alerts
    latest = backups[-1]
    age = datetime.now() - datetime.fromisoformat(latest.name.split("_")[-1])
    if age > timedelta(days=7):
        alerts.append({
            "ts": datetime.now().isoformat(),
            "type": "backup_age",
            "message": f"Backup más reciente tiene {age.days} días",
        })
    return alerts


def check_interactions_growth() -> List[Dict[str, Any]]:
    alerts = []
    if INTERACTIONS_FILE.exists():
        count = sum(1 for _ in open(INTERACTIONS_FILE, "r", encoding="utf-8"))
        if count > 10000:
            alerts.append({
                "ts": datetime.now().isoformat(),
                "type": "interactions_growth",
                "message": f"interactions.jsonl tiene {count} entradas sin filtrar",
            })
    return alerts


def check_health_providers() -> List[Dict[str, Any]]:
    alerts = []
    if not HEALTH_FILE.exists():
        return alerts
    try:
        records = load_jsonl(HEALTH_FILE)
        if not records:
            return alerts
        last = records[-1]
        ai = last.get("ai", {})
        for provider, status in ai.items():
            if isinstance(status, dict) and not status.get("ok", True):
                alerts.append({
                    "ts": datetime.now().isoformat(),
                    "type": "provider_down",
                    "message": f"Provider {provider} caído: {status.get('error', 'unknown')}",
                })
    except Exception:
        pass
    return alerts


def check_wifi_anomalies() -> List[Dict[str, Any]]:
    alerts = []
    wifi_file = ROOT / "logs" / "wifi_latest.json"
    if not wifi_file.exists():
        return alerts
    try:
        data = json.loads(wifi_file.read_text(encoding="utf-8"))
        anomalies = data.get("anomalies", [])
        for a in anomalies:
            alerts.append({
                "ts": datetime.now().isoformat(),
                "type": "wifi_anomaly",
                "message": f"WiFi anomaly: {a.get('type')} BSSID {a.get('bssid')}",
            })
        motion = data.get("motion", [])
        if motion:
            alerts.append({
                "ts": datetime.now().isoformat(),
                "type": "wifi_motion",
                "message": f"Movimiento WiFi detectado ({len(motion)} variaciones RSSI)",
            })
    except Exception:
        pass
    return alerts


def check_earthquake_risk() -> List[Dict[str, Any]]:
    alerts = []
    eq_file = ROOT / "logs" / "earthquakes_latest.json"
    if not eq_file.exists():
        return alerts
    try:
        data = json.loads(eq_file.read_text(encoding="utf-8"))
        risk = data.get("risk", {})
        level = risk.get("level", "low")
        if level in ("high", "critical"):
            alerts.append({
                "ts": datetime.now().isoformat(),
                "type": "earthquake_risk",
                "message": f"Riesgo sísmico {level}: score {risk.get('score', 0):.3f} | {risk.get('factors', [])}",
            })
    except Exception:
        pass
    return alerts


def main() -> int:
    metrics = load_jsonl(LOGS_DIR / "metrics.jsonl")
    alerts: List[Dict[str, Any]] = []
    alerts.extend(check_error_rate(metrics))
    alerts.extend(check_backup_age())
    alerts.extend(check_interactions_growth())
    alerts.extend(check_health_providers())
    alerts.extend(check_wifi_anomalies())
    alerts.extend(check_earthquake_risk())

    for alert in alerts:
        save_alert(alert)
        logger.warning("ALERTA: %s", alert["message"])
        send_external(alert)

    if not alerts:
        logger.info("Sin alertas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())