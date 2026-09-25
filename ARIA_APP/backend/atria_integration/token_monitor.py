"""Token Monitor - Monitorea gasto de tokens Atria."""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

class TokenMonitor:
    """Monitorea tokens y alerta sobre gasto."""

    def __init__(self, atria_client):
        self.client = atria_client
        self.alerts = []
        self.budget_warnings = []

    def check_budget(self) -> Dict[str, Any]:
        status = self.client.get_token_status()
        monthly_pct = status.get("monthly_percentage", 0)

        if monthly_pct > 80:
            warning = {
                "level": "CRITICAL",
                "message": f"Presupuesto mensual al {monthly_pct:.1f}%",
                "timestamp": datetime.now().isoformat(),
            }
            self.budget_warnings.append(warning)
        elif monthly_pct > 50:
            warning = {
                "level": "WARNING",
                "message": f"Presupuesto al {monthly_pct:.1f}%",
                "timestamp": datetime.now().isoformat(),
            }
            self.budget_warnings.append(warning)

        return status

    def should_continue(self) -> bool:
        status = self.client.get_token_status()
        monthly_pct = status.get("monthly_percentage", 0)
        return monthly_pct < 90

    def get_alerts(self) -> list:
        return self.budget_warnings[-10:]

    def get_dashboard(self) -> Dict[str, Any]:
        status = self.client.get_token_status()
        roi = self.client.get_roi_report()
        return {
            "token_status": status,
            "roi_report": roi,
            "alerts": self.get_alerts(),
            "can_continue": self.should_continue(),
        }

