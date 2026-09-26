#!/usr/bin/env python3
"""
predictive_maintenance.py — AURA Predictive Maintenance Engine
=================================================================
Motor de regresión lineal que analiza telemetría histórica para predecir
fallos de nodos antes de que ocurran.

Modelos de regresión (scikit-learn LinearRegression):
  - battery_degradation: Predice cuándo la batería llegará a 0%
  - ssh_latency_trend:    Predice cuándo la latencia del túnel superará el umbral crítico
  - signal_degradation:   Predice cuándo la señal Wi-Fi será insuficiente

Alerta preventiva: Si se predice FALLO en las próximas 4 horas → notifica a Discord.
"""

import os
import sys
import json
import time
import logging
import threading
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque

# ── scikit-learn para regresión lineal ──
try:
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import mean_absolute_error, r2_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    LinearRegression = None

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [PREDICTIVE-MAINT] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('predictive_maintenance.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Constantes ──
HISTORY_WINDOW_HOURS = 24      # Ventana de datos para entrenar modelo
PREDICTION_WINDOW_HOURS = 4    # Ventana de predicción (4h)
MIN_SAMPLES = 5                # Mínimo de muestras para entrenar
BATTERY_CRITICAL = 15          # Batería crítica (%)
LATENCY_CRITICAL_MS = 5000     # Latencia crítica (ms)
SIGNAL_CRITICAL = 20           # Señal mínima (%)
SIGNAL_DEGRADATION_DAYS = 7    # Días de señal para tendencia
CHECK_INTERVAL = 300            # Revisar cada 5 minutos

# ─── Tipos de predicción ───
class PredictionType:
    BATTERY = "battery"
    LATENCY = "latency"
    SIGNAL = "signal"

@dataclass
class PredictionResult:
    node_id: str
    prediction_type: str
    hours_to_failure: float
    confidence: float
    current_value: float
    threshold: float
    slope: float
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class PredictiveMaintenanceEngine:
    """
    Motor de mantenimiento predictivo.
    Usa regresión lineal (scikit-learn) sobre datos históricos de telemetría
    para predecir degradación de batería, latencia de túnel y señal Wi-Fi.
    """

    def __init__(self, notification_bridge=None, db_path: str = None):
        self.bridge = notification_bridge
        self.running = False
        self.check_thread = None

        # Almacén de telemetría por nodo
        # node_id -> { "battery": [(timestamp, value), ...],
        #              "latency": [(timestamp, value), ...],
        #              "signal":  [(timestamp, value), ...] }
        self.telemetry: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        self.last_alerts: Dict[str, float] = {}  # node_id+type -> timestamp (para evitar spam)

        # Cargar datos históricos si existen
        self._load_history()

        # Verificar disponibilidad de sklearn
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn no instalado. Usando regresión manual simplificada.")
        else:
            logger.info("scikit-learn disponible para regresión lineal.")

        logger.info("Predictive Maintenance Engine inicializado.")

    # ─── API Pública ───

    def record_battery(self, node_id: str, level: float):
        """Registra un dato de batería."""
        self.telemetry[node_id]["battery"].append((time.time(), level))
        self._trim_data(node_id, "battery")

    def record_latency(self, node_id: str, latency_ms: float):
        """Registra un dato de latencia de túnel SSH."""
        self.telemetry[node_id]["latency"].append((time.time(), latency_ms))
        self._trim_data(node_id, "latency")

    def record_signal(self, node_id: str, strength: float):
        """Registra un dato de intensidad de señal."""
        self.telemetry[node_id]["signal"].append((time.time(), strength))
        self._trim_data(node_id, "signal")

    def predict_node_failure(self, node_id: str) -> List[PredictionResult]:
        """
        Ejecuta todos los modelos de predicción para un nodo.
        Retorna lista de resultados (uno por métrica).
        """
        results = []

        # Batería
        bat_result = self._predict_metric(
            node_id, PredictionType.BATTERY,
            self.telemetry[node_id].get("battery", []),
            BATTERY_CRITICAL,
            "batería", "%"
        )
        if bat_result:
            results.append(bat_result)

        # Latencia
        lat_result = self._predict_metric(
            node_id, PredictionType.LATENCY,
            self.telemetry[node_id].get("latency", []),
            LATENCY_CRITICAL_MS,
            "latencia del túnel SSH", "ms",
            higher_is_worse=True
        )
        if lat_result:
            results.append(lat_result)

        # Señal
        sig_result = self._predict_metric(
            node_id, PredictionType.SIGNAL,
            self.telemetry[node_id].get("signal", []),
            SIGNAL_CRITICAL,
            "señal Wi-Fi", "%"
        )
        if sig_result:
            results.append(sig_result)

        return results

    def predict_all_nodes(self) -> Dict[str, List[PredictionResult]]:
        """Ejecuta predicción para todos los nodos con datos."""
        all_predictions = {}
        for node_id in list(self.telemetry.keys()):
            results = self.predict_node_failure(node_id)
            if results:
                all_predictions[node_id] = results
        return all_predictions

    def _predict_metric(self, node_id: str, metric_type: str,
                        data: list, threshold: float,
                        metric_name: str, unit: str,
                        higher_is_worse: bool = False) -> Optional[PredictionResult]:
        """
        Modelo de regresión lineal para una métrica.
        Retorna PredictionResult si se predice fallo dentro de PREDICTION_WINDOW_HOURS.
        """
        if len(data) < MIN_SAMPLES:
            return None

        # Preparar datos
        now = time.time()
        window_start = now - (HISTORY_WINDOW_HOURS * 3600)
        filtered = [(t, v) for t, v in data if t >= window_start]

        if len(filtered) < MIN_SAMPLES:
            return None

        # Convertir a arrays para regresión
        X = np.array([(t - now) / 3600 for t, v in filtered]).reshape(-1, 1)  # horas desde ahora
        y = np.array([v for t, v in filtered])

        if SKLEARN_AVAILABLE:
            # Regresión con scikit-learn
            model = LinearRegression()
            model.fit(X, y)
            slope = model.coef_[0]
            intercept = model.intercept_
            y_pred = model.predict(X)
            confidence = max(0, min(1, r2_score(y, y_pred))) if len(y) > 2 else 0.3
        else:
            # Regresión manual (mínimos cuadrados)
            n = len(X)
            x_mean = np.mean(X)
            y_mean = np.mean(y)
            numerator = np.sum((X.flatten() - x_mean) * (y - y_mean))
            denominator = np.sum((X.flatten() - x_mean) ** 2)
            slope = numerator / denominator if denominator != 0 else 0
            intercept = y_mean - slope * x_mean
            confidence = 0.4  # Valor fijo para regresión manual

        # Valor actual (último dato)
        current_value = filtered[-1][1]

        # Determinar si la tendencia es hacia el fallo
        if higher_is_worse:
            # Latencia: aumentar es malo
            if slope <= 0:
                return None  # No empeora
            hours_to_threshold = (threshold - intercept) / slope if slope > 0 else float('inf')
        else:
            # Batería/señal: disminuir es malo
            if slope >= 0:
                return None  # No empeora
            hours_to_threshold = (threshold - intercept) / slope if slope < 0 else float('inf')

        if hours_to_threshold <= 0 or hours_to_threshold == float('inf'):
            return None

        # ¿Fallo previsto dentro de las próximas 4 horas?
        if hours_to_threshold > PREDICTION_WINDOW_HOURS:
            return None  # Fuera de ventana de alerta

        # Generar mensaje descriptivo
        direction = "aumento" if higher_is_worse else "caída"
        message = (
            f"Nodo {node_id}: {metric_name} en {direction} crítico. "
            f"Valor actual: {current_value:.1f}{unit}, "
            f"umbral: {threshold}{unit}, "
            f"fallo previsto en {hours_to_threshold:.1f}h. "
            f"(pendiente: {slope:.3f}{unit}/h)"
        )

        result = PredictionResult(
            node_id=node_id,
            prediction_type=metric_type,
            hours_to_failure=round(hours_to_threshold, 2),
            confidence=round(confidence, 3),
            current_value=round(current_value, 1),
            threshold=threshold,
            slope=round(slope, 4),
            message=message
        )

        logger.warning(f"⚠️ PREDICCIÓN: {message}")
        return result

    def _trim_data(self, node_id: str, metric: str):
        """Mantiene solo datos de las últimas 48 horas."""
        cutoff = time.time() - (HISTORY_WINDOW_HOURS * 2 * 3600)
        self.telemetry[node_id][metric] = [
            (t, v) for t, v in self.telemetry[node_id][metric] if t >= cutoff
        ]

    # ─── Persistencia ───

    def _history_path(self) -> Path:
        return Path(__file__).resolve().parent / "predictive_history.json"

    def _load_history(self):
        """Carga datos históricos desde archivo JSON."""
        path = self._history_path()
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                for node_id, metrics in data.items():
                    for metric, values in metrics.items():
                        self.telemetry[node_id][metric] = [
                            (t, v) for t, v in values
                        ]
                logger.info(f"Datos históricos cargados: {len(self.telemetry)} nodos")
            except Exception as e:
                logger.error(f"Error cargando historial: {e}")

    def _save_history(self):
        """Guarda datos históricos a archivo JSON."""
        try:
            data = {}
            for node_id, metrics in self.telemetry.items():
                data[node_id] = {}
                for metric, values in metrics.items():
                    data[node_id][metric] = values[-200:]  # Últimos 200 puntos
            path = self._history_path()
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando historial: {e}")

    # ─── Bucle de monitoreo ───

    def _check_loop(self):
        """Bucle periódico que revisa predicciones y dispara alertas."""
        while self.running:
            try:
                logger.info("Ejecutando ciclo de mantenimiento predictivo...")
                predictions = self.predict_all_nodes()

                for node_id, results in predictions.items():
                    for pred in results:
                        # Evitar spam: misma alerta cada 30 minutos mínimo
                        alert_key = f"{node_id}_{pred.prediction_type}"
                        last_time = self.last_alerts.get(alert_key, 0)
                        if time.time() - last_time < 1800:  # 30 min
                            continue

                        # Disparar alerta preventiva
                        self._dispatch_alert(node_id, pred)
                        self.last_alerts[alert_key] = time.time()

            except Exception as e:
                logger.error(f"Error en ciclo predictivo: {e}")

            # Guardar datos periódicamente
            self._save_history()

            time.sleep(CHECK_INTERVAL)

    def _dispatch_alert(self, node_id: str, prediction: PredictionResult):
        """Envía alerta preventiva a Discord vía NotificationBridge."""
        title_map = {
            PredictionType.BATTERY: "⚠️ PREDICCIÓN: FALLO DE BATERÍA INMINENTE",
            PredictionType.LATENCY: "⚠️ PREDICCIÓN: FALLO DE RED INMINENTE",
            PredictionType.SIGNAL:  "⚠️ PREDICCIÓN: FALLO DE SEÑAL INMINENTE",
        }
        title = title_map.get(prediction.prediction_type,
                              "⚠️ PREDICCIÓN: FALLO DE NODO INMINENTE")

        logger.critical(f"🚨 {title} — {prediction.message}")

        if self.bridge:
            try:
                self.bridge.notify_threat_blocked(
                    threat_type=f"predictive_{prediction.prediction_type}_failure",
                    source="predictive_maintenance",
                    target=node_id,
                    severity="high" if prediction.hours_to_failure > 1 else "critical"
                )
                # También podemos enviar un mensaje directo a Discord
                logger.info(f"Alerta preventiva enviada para {node_id}")
            except Exception as e:
                logger.error(f"Error enviando alerta: {e}")
        else:
            logger.info(f"[Alerta simulada] {title}: {prediction.message}")

    # ─── Ciclo de Vida ───

    def start(self):
        if self.running:
            return
        self.running = True
        self.check_thread = threading.Thread(target=self._check_loop, daemon=True)
        self.check_thread.start()
        logger.info("Predictive Maintenance Engine iniciado (check cada 5 min)")

    def stop(self):
        self.running = False
        self._save_history()
        if self.check_thread:
            self.check_thread.join(timeout=10)
        logger.info("Predictive Maintenance Engine detenido")

    def get_status(self) -> Dict:
        return {
            "running": self.running,
            "nodes_tracked": len(self.telemetry),
            "sklearn_available": SKLEARN_AVAILABLE,
            "total_samples": sum(
                len(v) for metrics in self.telemetry.values()
                for v in metrics.values()
            ),
            "alert_cooldown_seconds": 1800
        }


# ═══════════════════════════════════════════════
# SIMULACIÓN Y DEMO
# ═══════════════════════════════════════════════

def simulate_telemetry(engine: PredictiveMaintenanceEngine):
    """Genera datos de telemetría simulados para demostración."""
    import random
    logger.info("Generando datos de telemetría simulados...")

    now = time.time()
    nodes = ["nodo-alpha", "nodo-beta", "nodo-gamma", "nodo-delta"]

    for node_id in nodes:
        # Batería: decreciente (simula degradación)
        base_battery = random.uniform(30, 90)
        for i in range(30):  # 30 muestras en 6 horas
            t = now - (i * 720)  # cada 12 minutos
            battery = base_battery - i * random.uniform(0.5, 2.0)
            battery = max(0, min(100, battery))
            engine.record_battery(node_id, battery)

        # Latencia: creciente (simula degradación de túnel)
        base_latency = random.uniform(100, 500)
        for i in range(30):
            t = now - (i * 720)
            latency = base_latency + i * random.uniform(20, 100)
            latency = max(0, latency)
            engine.record_latency(node_id, latency)

        # Señal: decreciente
        base_signal = random.uniform(40, 90)
        for i in range(30):
            t = now - (i * 720)
            signal = base_signal - i * random.uniform(0.3, 1.5)
            signal = max(0, min(100, signal))
            engine.record_signal(node_id, signal)

    logger.info(f"Datos simulados generados para {len(nodes)} nodos.")


# ─── Punto de entrada ───
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AURA Predictive Maintenance Engine")
    parser.add_argument("--demo", action="store_true", help="Ejecutar demo con datos simulados")
    parser.add_argument("--predict", type=str, metavar="NODE_ID",
                        help="Predecir fallo para un nodo específico")
    parser.add_argument("--status", action="store_true", help="Mostrar estado del motor")
    parser.add_argument("--check-all", action="store_true", help="Predecir para todos los nodos")
    args = parser.parse_args()

    engine = PredictiveMaintenanceEngine()

    if args.demo or args.predict or args.check_all:
        # Si no hay datos, generar simulados
        if not engine.telemetry:
            simulate_telemetry(engine)

    if args.predict:
        results = engine.predict_node_failure(args.predict)
        print(f"\n📊 Predicciones para {args.predict}:")
        print("=" * 60)
        if results:
            for r in results:
                icon = "🔴" if r.hours_to_failure < 2 else "🟡"
                print(f"\n{icon} Tipo: {r.prediction_type}")
                print(f"   Valor actual: {r.current_value} (umbral: {r.threshold})")
                print(f"   Horas hasta fallo: {r.hours_to_failure}h")
                print(f"   Confianza: {r.confidence:.1%}")
                print(f"   Pendiente: {r.slope}")
                print(f"   Mensaje: {r.message}")
        else:
            print("  ✅ Sin predicciones de fallo inminente.")

    if args.check_all:
        predictions = engine.predict_all_nodes()
        print("\n📊 PREDICCIONES GLOBALES")
        print("=" * 60)
        if predictions:
            for node_id, results in predictions.items():
                criticals = [r for r in results if r.hours_to_failure < 2]
                warnings = [r for r in results if 2 <= r.hours_to_failure <= 4]
                if criticals:
                    print(f"\n🔴 {node_id}: {len(criticals)} ALERTAS CRÍTICAS")
                    for r in criticals:
                        print(f"   • [{r.prediction_type}] Fallo en {r.hours_to_failure:.1f}h")
                if warnings:
                    print(f"\n🟡 {node_id}: {len(warnings)} ADVERTENCIAS")
                    for r in warnings:
                        print(f"   • [{r.prediction_type}] Fallo en {r.hours_to_failure:.1f}h")
                if not criticals and not warnings:
                    print(f"\n✅ {node_id}: Sin predicciones de fallo en 4h")
        else:
            print("  No hay suficientes datos para predicciones.")

    if args.demo:
        print("\n🎮 Demo: ejecutando predicciones sobre datos simulados...")
        engine.start()
        predictions = engine.predict_all_nodes()
        print(f"\nNodos con predicciones: {len(predictions)}")
        for node_id, results in predictions.items():
            for r in results:
                print(f"  {node_id}: {r.prediction_type} → fallo en {r.hours_to_failure:.1f}h")
        print("\nMotor predictivo ejecutándose en segundo plano (Ctrl+C para salir)...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            engine.stop()

    if args.status:
        status = engine.get_status()
        print("\n📊 ESTADO DEL MOTOR PREDICTIVO")
        print("=" * 40)
        for k, v in status.items():
            print(f"  {k}: {v}")

    if not any([args.demo, args.predict, args.check_all, args.status]):
        print("=" * 55)
        print("  AURA Predictive Maintenance Engine")
        print("=" * 55)
        print()
        print("  Uso:")
        print("    --demo          Demo con datos simulados")
        print("    --predict ID    Predecir fallo para un nodo")
        print("    --check-all     Predecir para todos los nodos")
        print("    --status        Estado del motor")
        print()
        print("  Ejemplo:")
        print("    python predictive_maintenance.py --demo")
        print("    python predictive_maintenance.py --predict nodo-alpha")
        print("    python predictive_maintenance.py --check-all")