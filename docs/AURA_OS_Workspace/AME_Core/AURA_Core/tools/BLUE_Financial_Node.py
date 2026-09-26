import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

# --- CONFIGURACIÓN DE ARQUITECTURA AURA_CORE ---
AURA_CORE_PATH = Path(__file__).parent.parent
LOGS_DIR = AURA_CORE_PATH / "logs"
STATS_FILE = LOGS_DIR / "farming_stats.json"

class BLUEFinancialNode:
    """El cerebro de negocios del ecosistema AURA/AME."""
    def __init__(self, stats_file_path=STATS_FILE):
        self.stats_file_path = stats_file_path
        print("[BLUE_Financial_Node] Inicializando nodo financiero...")
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

    def _leer_estadisticas_farming(self):
        if not self.stats_file_path.exists():
            return None
        try:
            with open(self.stats_file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Error al leer estadísticas: {e}")
            return None

    def _calcular_rentabilidad(self, stats_data):
        if not stats_data:
            return {"error": "Sin datos de estadísticas."}
        
        daily_hash = stats_data.get("daily_hash", 0)
        daily_coins = stats_data.get("daily_coins", 0.0)
        total_runtime_seconds = stats_data.get("total_runtime_seconds", 0)

        hash_per_second = daily_hash / total_runtime_seconds if total_runtime_seconds > 0 else 0
        coins_per_hour = daily_coins / (total_runtime_seconds / 3600) if total_runtime_seconds > 0 else 0
        uptime_hours = total_runtime_seconds / 3600
        uptime_percentage = (uptime_hours / 24) * 100 if uptime_hours > 0 else 0

        return {
            "analysis_date": datetime.now().isoformat(),
            "daily_performance": {
                "hash_earned": daily_hash,
                "coins_earned": daily_coins,
                "uptime_hours": round(uptime_hours, 2),
                "uptime_percentage": round(uptime_percentage, 2),
                "efficiency_hash_per_sec": round(hash_per_second, 2),
                "efficiency_coins_per_hour": round(coins_per_hour, 6)
            },
            "weekly_projection": {
                "projected_hash": daily_hash * 7,
                "projected_coins": round(daily_coins * 7, 6)
            },
            "status": "operational",
            "trend": "stable"
        }

    def escanear_oportunidades_nicho(self):
        return {
            "scan_status": "placeholder_active",
            "last_scan": datetime.now().isoformat(),
            "opportunities_found": 0,
            "message": "Módulo de escaneo preparado para futuras integraciones."
        }

    def generar_reporte_blue(self):
        print("[BLUE_Financial_Node] Generando reporte...")
        stats_data = self._leer_estadisticas_farming()
        financial_analysis = self._calcular_rentabilidad(stats_data)
        opportunity_scan = self.escanear_oportunidades_nicho()
        return {
            "node_name": "BLUE_Financial_Node",
            "report_version": "1.0",
            "financial_analysis": financial_analysis,
            "opportunity_scan": opportunity_scan
        }