#!/usr/bin/env python3
"""
network_history_db.py — AURA Network History Database (SQLite)
==============================================================
Base de datos centralizada SQLite3 que indexa toda la actividad de la red.
Proporciona almacenamiento de eventos, análisis de tendencias y 
detección de anomalías para el ecosistema AURA.

Tablas:
  - events:       Registro cronológico de todas las acciones de red
  - nodes:        Estado histórico de nodos móviles
  - network_scans: Instantáneas periódicas de dispositivos en la red
  - anomalies:    Alertas de anomalías generadas por el análisis de tendencias
  - sync_log:     Registro de sincronización con nodos móviles

Funcionalidades:
  - Inserción y consulta de eventos históricos
  - Análisis de tendencias con detección de anomalías (+50% umbral)
  - Sincronización periódica con nodos móviles vía API/WebSocket
  - Cálculo de promedios móviles (ventana de 7 días)
  - Alertas automáticas cuando el número de dispositivos se desvía de la media
"""

import os
import sys
import json
import time
import sqlite3
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from collections import defaultdict, deque
import statistics
import math

# ── Configuración de logging ──
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [NETWORK-DB] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('network_history_db.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ── Constantes ──
DB_DIR = Path(__file__).resolve().parent
DB_PATH = DB_DIR / "network_history.db"
SYNC_INTERVAL = 300  # Sincronizar cada 5 minutos
ANOMALY_THRESHOLD = 0.50  # +50% respecto al promedio = anomalía
TREND_WINDOW_DAYS = 7     # Ventana de análisis de tendencias (7 días)
MAX_EVENTS_RETENTION = 100000  # Máximo de eventos antes de purgar


class NetworkHistoryDB:
    """
    Base de datos centralizada SQLite3 para el historial de red de AURA.
    Thread-safe con conexiones separadas por hilo.
    """
    
    def __init__(self, db_path: str = None, auto_init: bool = True):
        self.db_path = db_path or str(DB_PATH)
        self._local = threading.local()
        self.lock = threading.Lock()
        self.running = False
        self.sync_thread = None
        self.notification_bridge = None
        self.event_listeners: List[callable] = []
        
        if auto_init:
            self._initialize_db()
            logger.info(f"Network History DB inicializada en: {self.db_path}")
    
    @property
    def conn(self) -> sqlite3.Connection:
        """Obtiene una conexión SQLite para el hilo actual (thread-local)."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn
    
    def _initialize_db(self):
        """Crea las tablas si no existen."""
        with self.lock:
            conn = self.conn
            cursor = conn.cursor()
            
            # ── Tabla de Eventos ──
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'unknown',
                    result TEXT DEFAULT '',
                    severity TEXT DEFAULT 'info',
                    duration_ms INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            
            # ── Tabla de Nodos ──
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    name TEXT DEFAULT '',
                    ip_address TEXT DEFAULT '',
                    status TEXT DEFAULT 'unknown',
                    role TEXT DEFAULT 'mobile',
                    last_seen TEXT,
                    first_seen TEXT DEFAULT (datetime('now')),
                    battery_level REAL DEFAULT 0.0,
                    signal_strength REAL DEFAULT 0.0,
                    total_uptime_seconds INTEGER DEFAULT 0,
                    tasks_completed INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            # ── Tabla de Escaneos de Red ──
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS network_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    scan_type TEXT DEFAULT 'full',
                    total_devices INTEGER DEFAULT 0,
                    new_devices INTEGER DEFAULT 0,
                    unknown_devices INTEGER DEFAULT 0,
                    known_devices INTEGER DEFAULT 0,
                    offline_devices INTEGER DEFAULT 0,
                    networks_found INTEGER DEFAULT 0,
                    devices_data TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            
            # ── Tabla de Anomalías ──
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS anomalies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    anomaly_type TEXT NOT NULL,
                    severity TEXT DEFAULT 'medium',
                    metric_name TEXT NOT NULL,
                    current_value REAL NOT NULL,
                    expected_value REAL NOT NULL,
                    deviation_pct REAL NOT NULL,
                    threshold_pct REAL NOT NULL,
                    description TEXT DEFAULT '',
                    node_id TEXT DEFAULT '',
                    resolved BOOLEAN DEFAULT 0,
                    resolved_at TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            
            # ── Tabla de Sincronización ──
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    sync_type TEXT DEFAULT 'full',
                    events_synced INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'success',
                    error_message TEXT DEFAULT '',
                    duration_ms INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            
            # ── Índices para consultas rápidas ──
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_node ON events(node_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_action ON events(action)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scans_timestamp ON network_scans(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp ON anomalies(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_anomalies_type ON anomalies(anomaly_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_node ON sync_log(node_id)")
            
            conn.commit()
    
    # ══════════════════════════════════════════════════
    # EVENTOS
    # ══════════════════════════════════════════════════
    
    def insert_event(self, node_id: str, action: str, status: str = "unknown",
                     result: str = "", severity: str = "info",
                     duration_ms: int = 0, metadata: Dict = None) -> int:
        """Inserta un evento en la base de datos."""
        try:
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO events (timestamp, node_id, action, status, result, 
                                        severity, duration_ms, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    node_id, action, status, result,
                    severity, duration_ms,
                    json.dumps(metadata or {})
                ))
                self.conn.commit()
                event_id = cursor.lastrowid
                
                # Notificar a listeners
                self._notify_listeners({
                    "type": "event_inserted",
                    "id": event_id,
                    "node_id": node_id,
                    "action": action,
                    "status": status,
                    "severity": severity
                })
                
                # Purgar eventos viejos si es necesario
                self._maybe_purge_events()
                
                return event_id
        except Exception as e:
            logger.error(f"Error insertando evento: {e}")
            return -1
    
    def query_events(self, node_id: str = None, action: str = None,
                     status: str = None, severity: str = None,
                     start_time: str = None, end_time: str = None,
                     limit: int = 100, offset: int = 0) -> List[Dict]:
        """Consulta eventos con filtros."""
        try:
            conditions = []
            params = []
            
            if node_id:
                conditions.append("node_id = ?")
                params.append(node_id)
            if action:
                conditions.append("action = ?")
                params.append(action)
            if status:
                conditions.append("status = ?")
                params.append(status)
            if severity:
                conditions.append("severity = ?")
                params.append(severity)
            if start_time:
                conditions.append("timestamp >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("timestamp <= ?")
                params.append(end_time)
            
            where = " AND ".join(conditions) if conditions else "1=1"
            
            cursor = self.conn.cursor()
            cursor.execute(f"""
                SELECT * FROM events 
                WHERE {where}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """, params + [limit, offset])
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error consultando eventos: {e}")
            return []
    
    def get_event_count(self, node_id: str = None, action: str = None,
                        since: str = None) -> int:
        """Cuenta eventos con filtros."""
        try:
            conditions = []
            params = []
            if node_id:
                conditions.append("node_id = ?")
                params.append(node_id)
            if action:
                conditions.append("action = ?")
                params.append(action)
            if since:
                conditions.append("timestamp >= ?")
                params.append(since)
            
            where = " AND ".join(conditions) if conditions else "1=1"
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM events WHERE {where}", params)
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error contando eventos: {e}")
            return 0
    
    def _maybe_purge_events(self):
        """Purga eventos antiguos si se supera el límite."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM events")
            count = cursor.fetchone()[0]
            
            if count > MAX_EVENTS_RETENTION:
                # Eliminar los eventos más antiguos
                cursor.execute("""
                    DELETE FROM events WHERE id IN (
                        SELECT id FROM events 
                        ORDER BY timestamp ASC 
                        LIMIT ?
                    )
                """, (count - MAX_EVENTS_RETENTION,))
                self.conn.commit()
                logger.info(f"Eventos purgados: {count - MAX_EVENTS_RETENTION}")
        except Exception as e:
            logger.error(f"Error purgando eventos: {e}")
    
    # ══════════════════════════════════════════════════
    # NODOS
    # ══════════════════════════════════════════════════
    
    def upsert_node(self, node_id: str, name: str = "", ip_address: str = "",
                    status: str = "unknown", role: str = "mobile",
                    battery_level: float = 0.0, signal_strength: float = 0.0,
                    metadata: Dict = None) -> bool:
        """Inserta o actualiza un nodo en la base de datos."""
        try:
            with self.lock:
                cursor = self.conn.cursor()
                
                # Verificar si el nodo existe
                cursor.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
                existing = cursor.fetchone()
                
                if existing:
                    # Actualizar
                    cursor.execute("""
                        UPDATE nodes SET
                            name = ?,
                            ip_address = ?,
                            status = ?,
                            role = ?,
                            last_seen = ?,
                            battery_level = ?,
                            signal_strength = ?,
                            total_uptime_seconds = total_uptime_seconds + ?,
                            metadata = ?
                        WHERE id = ?
                    """, (
                        name, ip_address, status, role,
                        datetime.now().isoformat(),
                        battery_level, signal_strength,
                        60,  # +1 minuto de uptime
                        json.dumps(metadata or {}),
                        node_id
                    ))
                else:
                    # Insertar
                    cursor.execute("""
                        INSERT INTO nodes (id, name, ip_address, status, role, 
                                           last_seen, battery_level, signal_strength,
                                           metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        node_id, name, ip_address, status, role,
                        datetime.now().isoformat(),
                        battery_level, signal_strength,
                        json.dumps(metadata or {})
                    ))
                
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error actualizando nodo {node_id}: {e}")
            return False
    
    def get_nodes(self, status: str = None) -> List[Dict]:
        """Obtiene todos los nodos, opcionalmente filtrados por estado."""
        try:
            cursor = self.conn.cursor()
            if status:
                cursor.execute("SELECT * FROM nodes WHERE status = ? ORDER BY last_seen DESC", (status,))
            else:
                cursor.execute("SELECT * FROM nodes ORDER BY last_seen DESC")
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error obteniendo nodos: {e}")
            return []
    
    # ══════════════════════════════════════════════════
    # ESCANEOS DE RED
    # ══════════════════════════════════════════════════
    
    def insert_network_scan(self, scan_type: str, total_devices: int,
                            new_devices: int = 0, unknown_devices: int = 0,
                            known_devices: int = 0, offline_devices: int = 0,
                            networks_found: int = 0,
                            devices_data: List[Dict] = None) -> int:
        """Registra un escaneo de red completo."""
        try:
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO network_scans 
                    (timestamp, scan_type, total_devices, new_devices, 
                     unknown_devices, known_devices, offline_devices,
                     networks_found, devices_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    scan_type, total_devices, new_devices,
                    unknown_devices, known_devices, offline_devices,
                    networks_found,
                    json.dumps(devices_data or [])
                ))
                self.conn.commit()
                scan_id = cursor.lastrowid
                
                # Verificar anomalía después de insertar
                self._check_scan_anomaly(total_devices)
                
                return scan_id
        except Exception as e:
            logger.error(f"Error insertando escaneo: {e}")
            return -1
    
    def get_recent_scans(self, limit: int = 10) -> List[Dict]:
        """Obtiene los últimos escaneos de red."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM network_scans 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error obteniendo escaneos recientes: {e}")
            return []
    
    def get_device_count_average(self, days: int = TREND_WINDOW_DAYS) -> float:
        """Calcula el promedio de dispositivos en los últimos N días."""
        try:
            since = (datetime.now() - timedelta(days=days)).isoformat()
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT AVG(total_devices) FROM network_scans 
                WHERE timestamp >= ?
            """, (since,))
            result = cursor.fetchone()[0]
            return round(result or 0.0, 2)
        except Exception as e:
            logger.error(f"Error calculando promedio: {e}")
            return 0.0
    
    def get_device_count_std_dev(self, days: int = TREND_WINDOW_DAYS) -> float:
        """Calcula la desviación estándar del número de dispositivos."""
        try:
            since = (datetime.now() - timedelta(days=days)).isoformat()
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT total_devices FROM network_scans 
                WHERE timestamp >= ?
            """, (since,))
            values = [row[0] for row in cursor.fetchall()]
            
            if len(values) < 2:
                return 0.0
            
            return round(statistics.stdev(values), 2)
        except Exception as e:
            logger.error(f"Error calculando desviación estándar: {e}")
            return 0.0
    
    def _check_scan_anomaly(self, current_devices: int):
        """
        Verifica si el número actual de dispositivos constituye una anomalía.
        Gatillo: desviación > +50% respecto al promedio histórico.
        """
        try:
            avg = self.get_device_count_average()
            
            if avg <= 0 or current_devices <= 0:
                return  # No hay datos suficientes para comparar
            
            deviation_pct = (current_devices - avg) / avg
            
            # Solo alertar si hay un aumento significativo (+50%)
            if deviation_pct >= ANOMALY_THRESHOLD:
                description = (
                    f"Dispositivos detectados: {current_devices} "
                    f"(promedio histórico: {avg:.1f}, "
                    f"desviación: {deviation_pct*100:.1f}%, "
                    f"umbral: {ANOMALY_THRESHOLD*100:.0f}%)"
                )
                
                self.insert_anomaly(
                    anomaly_type="device_count_spike",
                    severity="high",
                    metric_name="total_devices",
                    current_value=float(current_devices),
                    expected_value=avg,
                    deviation_pct=round(deviation_pct * 100, 1),
                    threshold_pct=ANOMALY_THRESHOLD * 100,
                    description=description
                )
                
                logger.warning(f"⚠️ ANOMALÍA DETECTADA: {description}")
                
            elif deviation_pct <= -ANOMALY_THRESHOLD:
                # También alertar si hay una disminución significativa
                description = (
                    f"Caída en dispositivos detectados: {current_devices} "
                    f"(promedio histórico: {avg:.1f}, "
                    f"desviación: {deviation_pct*100:.1f}%)"
                )
                
                self.insert_anomaly(
                    anomaly_type="device_count_drop",
                    severity="medium",
                    metric_name="total_devices",
                    current_value=float(current_devices),
                    expected_value=avg,
                    deviation_pct=round(abs(deviation_pct) * 100, 1),
                    threshold_pct=ANOMALY_THRESHOLD * 100,
                    description=description
                )
                
        except Exception as e:
            logger.error(f"Error verificando anomalía de escaneo: {e}")
    
    # ══════════════════════════════════════════════════
    # ANOMALÍAS
    # ══════════════════════════════════════════════════
    
    def insert_anomaly(self, anomaly_type: str, severity: str = "medium",
                       metric_name: str = "", current_value: float = 0.0,
                       expected_value: float = 0.0, deviation_pct: float = 0.0,
                       threshold_pct: float = 50.0, description: str = "",
                       node_id: str = "") -> int:
        """Registra una anomalía en la base de datos."""
        try:
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO anomalies 
                    (timestamp, anomaly_type, severity, metric_name,
                     current_value, expected_value, deviation_pct,
                     threshold_pct, description, node_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    anomaly_type, severity, metric_name,
                    current_value, expected_value, deviation_pct,
                    threshold_pct, description, node_id
                ))
                self.conn.commit()
                anomaly_id = cursor.lastrowid
                
                # Notificar a listeners
                self._notify_listeners({
                    "type": "anomaly_detected",
                    "id": anomaly_id,
                    "anomaly_type": anomaly_type,
                    "severity": severity,
                    "description": description,
                    "deviation_pct": deviation_pct
                })
                
                # Si hay un bridge de notificaciones, enviar alerta
                if self.notification_bridge:
                    try:
                        if severity in ("high", "critical"):
                            self.notification_bridge.notify_threat_blocked(
                                threat_type=f"anomaly_{anomaly_type}",
                                source="network_history_db",
                                target=node_id or "network"
                            )
                    except Exception as notify_err:
                        logger.error(f"Error notificando anomalía: {notify_err}")
                
                return anomaly_id
        except Exception as e:
            logger.error(f"Error insertando anomalía: {e}")
            return -1
    
    def get_anomalies(self, severity: str = None, anomaly_type: str = None,
                      since: str = None, limit: int = 50) -> List[Dict]:
        """Obtiene anomalías con filtros."""
        try:
            conditions = []
            params = []
            
            if severity:
                conditions.append("severity = ?")
                params.append(severity)
            if anomaly_type:
                conditions.append("anomaly_type = ?")
                params.append(anomaly_type)
            if since:
                conditions.append("timestamp >= ?")
                params.append(since)
            
            where = " AND ".join(conditions) if conditions else "1=1"
            
            cursor = self.conn.cursor()
            cursor.execute(f"""
                SELECT * FROM anomalies 
                WHERE {where}
                ORDER BY timestamp DESC
                LIMIT ?
            """, params + [limit])
            
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error obteniendo anomalías: {e}")
            return []
    
    def resolve_anomaly(self, anomaly_id: int) -> bool:
        """Marca una anomalía como resuelta."""
        try:
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    UPDATE anomalies SET 
                        resolved = 1, 
                        resolved_at = datetime('now')
                    WHERE id = ?
                """, (anomaly_id,))
                self.conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error resolviendo anomalía {anomaly_id}: {e}")
            return False
    
    # ══════════════════════════════════════════════════
    # ANÁLISIS DE TENDENCIAS
    # ══════════════════════════════════════════════════
    
    def get_trend_analysis(self, days: int = TREND_WINDOW_DAYS) -> Dict:
        """
        Análisis completo de tendencias de la red.
        Compara el estado actual contra el histórico.
        """
        try:
            since = (datetime.now() - timedelta(days=days)).isoformat()
            cursor = self.conn.cursor()
            
            # ── Dispositivos ──
            cursor.execute("""
                SELECT AVG(total_devices), MAX(total_devices), MIN(total_devices),
                       COUNT(*)
                FROM network_scans WHERE timestamp >= ?
            """, (since,))
            scan_stats = cursor.fetchone()
            
            avg_devices = round(scan_stats[0] or 0, 1)
            max_devices = scan_stats[1] or 0
            min_devices = scan_stats[2] or 0
            total_scans = scan_stats[3] or 0
            
            # Último escaneo
            cursor.execute("""
                SELECT total_devices FROM network_scans 
                ORDER BY timestamp DESC LIMIT 1
            """)
            last_scan = cursor.fetchone()
            current_devices = last_scan[0] if last_scan else 0
            
            # ── Eventos ──
            cursor.execute("""
                SELECT action, COUNT(*) as cnt FROM events 
                WHERE timestamp >= ? 
                GROUP BY action ORDER BY cnt DESC
            """, (since,))
            top_actions = {row[0]: row[1] for row in cursor.fetchall()}
            
            cursor.execute("""
                SELECT status, COUNT(*) as cnt FROM events 
                WHERE timestamp >= ? 
                GROUP BY status
            """, (since,))
            status_distribution = {row[0]: row[1] for row in cursor.fetchall()}
            
            # ── Anomalías ──
            cursor.execute("""
                SELECT anomaly_type, COUNT(*) as cnt FROM anomalies 
                WHERE timestamp >= ? AND resolved = 0
                GROUP BY anomaly_type
            """, (since,))
            active_anomalies = {row[0]: row[1] for row in cursor.fetchall()}
            
            # ── Nodos ──
            cursor.execute("""
                SELECT status, COUNT(*) as cnt FROM nodes 
                GROUP BY status
            """)
            node_status = {row[0]: row[1] for row in cursor.fetchall()}
            
            # ── Calcular desviación ──
            deviation_pct = 0.0
            if avg_devices > 0 and current_devices > 0:
                deviation_pct = round(
                    (current_devices - avg_devices) / avg_devices * 100, 1
                )
            
            # ── Detectar anomalía activa ──
            has_anomaly = deviation_pct >= ANOMALY_THRESHOLD * 100
            
            return {
                "analysis_date": datetime.now().isoformat(),
                "window_days": days,
                "total_scans": total_scans,
                "devices": {
                    "current": current_devices,
                    "average_7d": avg_devices,
                    "max_7d": max_devices,
                    "min_7d": min_devices,
                    "deviation_pct": deviation_pct,
                    "anomaly_detected": has_anomaly
                },
                "nodes": {
                    "total": sum(node_status.values()),
                    "by_status": node_status
                },
                "events": {
                    "total_7d": sum(top_actions.values()),
                    "top_actions": top_actions,
                    "status_distribution": status_distribution
                },
                "anomalies": {
                    "active": len(active_anomalies),
                    "by_type": active_anomalies
                }
            }
        except Exception as e:
            logger.error(f"Error en análisis de tendencias: {e}")
            return {"error": str(e)}
    
    # ══════════════════════════════════════════════════
    # SINCRONIZACIÓN CON NODOS MÓVILES
    # ══════════════════════════════════════════════════
    
    def sync_from_mobile(self, node_id: str, events: List[Dict]) -> int:
        """
        Sincroniza eventos desde un nodo móvil hacia la DB central.
        Retorna el número de eventos sincronizados.
        """
        synced = 0
        try:
            for event in events:
                self.insert_event(
                    node_id=event.get("node_id", node_id),
                    action=event.get("action", "unknown"),
                    status=event.get("status", "unknown"),
                    result=event.get("result", ""),
                    severity=event.get("severity", "info"),
                    duration_ms=event.get("duration_ms", 0),
                    metadata=event.get("metadata")
                )
                synced += 1
            
            # Registrar sincronización
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO sync_log 
                    (timestamp, node_id, sync_type, events_synced, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    node_id, "incremental", synced, "success"
                ))
                self.conn.commit()
            
            logger.info(f"Sincronizados {synced} eventos desde {node_id}")
            return synced
        except Exception as e:
            logger.error(f"Error sincronizando desde {node_id}: {e}")
            
            # Registrar error
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO sync_log 
                    (timestamp, node_id, sync_type, events_synced, status, error_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    node_id, "incremental", synced, "failed", str(e)
                ))
                self.conn.commit()
            return 0
    
    def get_pending_sync_data(self, node_id: str, since: str = None) -> Dict:
        """
        Obtiene datos pendientes para sincronizar hacia un nodo móvil.
        """
        if not since:
            since = (datetime.now() - timedelta(hours=1)).isoformat()
        
        return {
            "events": self.query_events(
                start_time=since, limit=500
            ),
            "nodes": self.get_nodes(),
            "anomalies": self.get_anomalies(since=since),
            "trends": self.get_trend_analysis()
        }
    
    def _sync_loop(self):
        """Bucle de sincronización periódica con nodos móviles."""
        while self.running:
            try:
                # Obtener nodos activos
                nodes = self.get_nodes(status="online")
                
                for node in nodes:
                    node_id = node["id"]
                    try:
                        # En un entorno real, aquí se haría una petición HTTP/WS
                        # al nodo móvil para obtener sus eventos pendientes
                        
                        # Simular sincronización (en producción conectar vía API)
                        logger.debug(f"Sincronizando con nodo {node_id}...")
                        
                        # Actualizar timestamp del nodo
                        self.upsert_node(
                            node_id=node_id,
                            status="online"
                        )
                        
                    except Exception as node_err:
                        logger.error(f"Error sincronizando nodo {node_id}: {node_err}")
                
            except Exception as e:
                logger.error(f"Error en bucle de sincronización: {e}")
            
            time.sleep(SYNC_INTERVAL)
    
    # ══════════════════════════════════════════════════
    # UTILIDADES
    # ══════════════════════════════════════════════════
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas generales de la base de datos."""
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM events")
            total_events = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM nodes")
            total_nodes = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM network_scans")
            total_scans = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM anomalies WHERE resolved = 0")
            active_anomalies = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM anomalies")
            total_anomalies = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM sync_log WHERE status = 'success'")
            successful_syncs = cursor.fetchone()[0]
            
            # Tamaño de la base de datos
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            return {
                "total_events": total_events,
                "total_nodes": total_nodes,
                "total_scans": total_scans,
                "total_anomalies": total_anomalies,
                "active_anomalies": active_anomalies,
                "successful_syncs": successful_syncs,
                "db_size_bytes": db_size,
                "db_size_mb": round(db_size / (1024 * 1024), 2),
                "db_path": self.db_path,
                "is_running": self.running
            }
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {"error": str(e)}
    
    def register_listener(self, callback: callable):
        """Registra un listener para eventos de la base de datos."""
        self.event_listeners.append(callback)
    
    def _notify_listeners(self, data: Dict):
        """Notifica a todos los listeners registrados."""
        for listener in self.event_listeners:
            try:
                listener(data)
            except Exception as e:
                logger.error(f"Error en listener: {e}")
    
    def set_notification_bridge(self, bridge):
        """Conecta con el NotificationBridge para alertas de anomalías."""
        self.notification_bridge = bridge
        logger.info("Notification Bridge conectado")
    
    # ══════════════════════════════════════════════════
    # CICLO DE VIDA
    # ══════════════════════════════════════════════════
    
    def start(self):
        """Inicia el servicio de base de datos y sincronización."""
        if self.running:
            logger.warning("Network History DB ya está en ejecución")
            return
        
        self.running = True
        
        # Iniciar hilo de sincronización
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        
        logger.info("Network History DB iniciada")
        logger.info(f"  DB Path: {self.db_path}")
        logger.info(f"  Sync interval: {SYNC_INTERVAL}s")
        logger.info(f"  Anomaly threshold: {ANOMALY_THRESHOLD*100:.0f}%")
        logger.info(f"  Trend window: {TREND_WINDOW_DAYS} días")
    
    def stop(self):
        """Detiene el servicio."""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=10)
        
        # Cerrar conexiones
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
        
        logger.info("Network History DB detenida")
    
    def __del__(self):
        self.stop()


# ══════════════════════════════════════════════════
# PUNTO DE ENTRADA
# ══════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AURA Network History Database")
    parser.add_argument("--init", action="store_true", help="Inicializar/verificar DB")
    parser.add_argument("--stats", action="store_true", help="Mostrar estadísticas")
    parser.add_argument("--trends", action="store_true", help="Mostrar análisis de tendencias")
    parser.add_argument("--anomalies", action="store_true", help="Mostrar anomalías activas")
    parser.add_argument("--test-scan", type=int, metavar="DEVICES", 
                        help="Insertar escaneo de prueba con N dispositivos")
    parser.add_argument("--demo", action="store_true", 
                        help="Ejecutar demostración con datos simulados")
    args = parser.parse_args()
    
    db = NetworkHistoryDB()
    
    if args.init:
        print("✅ Base de datos inicializada correctamente")
        print(f"   Path: {db.db_path}")
    
    if args.stats:
        stats = db.get_stats()
        print("\n📊 ESTADÍSTICAS DE LA BASE DE DATOS")
        print("=" * 40)
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    if args.trends:
        trends = db.get_trend_analysis()
        print("\n📈 ANÁLISIS DE TENDENCIAS")
        print("=" * 40)
        print(f"  Dispositivos actuales: {trends['devices']['current']}")
        print(f"  Promedio 7 días: {trends['devices']['average_7d']}")
        print(f"  Desviación: {trends['devices']['deviation_pct']}%")
        print(f"  ¿Anomalía?: {'⚠️ SÍ' if trends['devices']['anomaly_detected'] else '✅ No'}")
        print(f"  Eventos en 7 días: {trends['events']['total_7d']}")
        print(f"  Anomalías activas: {trends['anomalies']['active']}")
    
    if args.anomalies:
        anomalies = db.get_anomalies(limit=20)
        print(f"\n🚨 ANOMALÍAS ({len(anomalies)} encontradas)")
        print("=" * 40)
        for a in anomalies:
            status = "🔴 Activa" if not a["resolved"] else "✅ Resuelta"
            print(f"  [{a['severity'].upper()}] {a['anomaly_type']} — {status}")
            print(f"    Valor: {a['current_value']} | Esperado: {a['expected_value']} "
                  f"| Desviación: {a['deviation_pct']}%")
            print(f"    {a['description'][:100]}")
            print()
    
    if args.test_scan:
        devices = args.test_scan
        scan_id = db.insert_network_scan(
            scan_type="full",
            total_devices=devices,
            new_devices=max(0, devices - 5),
            unknown_devices=max(0, devices // 4),
            known_devices=max(0, devices - devices // 4)
        )
        print(f"✅ Escaneo insertado (ID: {scan_id}) con {devices} dispositivos")
        
        # Mostrar análisis post-inserción
        trends = db.get_trend_analysis()
        if trends['devices']['anomaly_detected']:
            print(f"\n⚠️ ¡ANOMALÍA DETECTADA!")
            print(f"  Desviación: {trends['devices']['deviation_pct']}%")
    
    if args.demo:
        print("\n🎮 EJECUTANDO DEMOSTRACIÓN...\n")
        
        # Insertar datos históricos de ejemplo
        print("Insertando datos históricos de ejemplo...")
        base_devices = 15
        for day in range(7):
            for scan in range(3):
                variation = int((day - 3) * 1.5 + scan * 0.5)
                devices = max(5, base_devices + variation)
                db.insert_network_scan(
                    scan_type="full" if scan == 0 else "quick",
                    total_devices=devices,
                    new_devices=max(0, devices - 10),
                    unknown_devices=max(0, devices // 5)
                )
        
        # Simular eventos de nodos
        print("Insertando eventos de ejemplo...")
        for i in range(50):
            db.insert_event(
                node_id=f"node-{(i % 5) + 1:02d}",
                action=["network_scan", "osint_scan", "threat_check", "telemetry"][i % 4],
                status=["success", "success", "failed", "success"][i % 4],
                severity=["info", "info", "warning", "info"][i % 4]
            )
        
        # Registrar nodos
        print("Registrando nodos...")
        for i in range(5):
            db.upsert_node(
                node_id=f"node-{i+1:02d}",
                name=f"Nodo Móvil {i+1}",
                ip_address=f"192.168.1.{100 + i}",
                status="online" if i != 3 else "offline",
                battery_level=70 + i * 5,
                signal_strength=60 + i * 8
            )
        
        # Mostrar resultados
        print("\n" + "=" * 50)
        print("RESULTADOS DE LA DEMOSTRACIÓN")
        print("=" * 50)
        
        stats = db.get_stats()
        print(f"\n📊 Estadísticas:")
        print(f"  Eventos: {stats['total_events']}")
        print(f"  Nodos: {stats['total_nodes']}")
        print(f"  Escaneos: {stats['total_scans']}")
        print(f"  Anomalías: {stats['total_anomalies']}")
        print(f"  DB Size: {stats['db_size_mb']} MB")
        
        trends = db.get_trend_analysis()
        print(f"\n📈 Tendencias:")
        print(f"  Dispositivos actuales: {trends['devices']['current']}")
        print(f"  Promedio 7d: {trends['devices']['average_7d']}")
        print(f"  Desviación: {trends['devices']['deviation_pct']}%")
        print(f"  Anomalía: {'⚠️ SÍ' if trends['devices']['anomaly_detected'] else '✅ No'}")
        
        # Insertar un escaneo con anomalía para probar la detección
        print(f"\n🧪 Insertando escaneo ANÓMALO ({int(base_devices * 1.7)} dispositivos)...")
        db.insert_network_scan(
            scan_type="full",
            total_devices=int(base_devices * 1.7),
            new_devices=int(base_devices * 0.7),
            unknown_devices=int(base_devices * 0.3)
        )
        
        # Mostrar anomalías detectadas
        anomalies = db.get_anomalies(limit=5)
        if anomalies:
            print(f"\n🚨 Anomalías detectadas ({len(anomalies)}):")
            for a in anomalies:
                print(f"  [{a['severity'].upper()}] {a['anomaly_type']}")
                print(f"    → {a['description'][:120]}")
        
        print("\n✅ Demostración completada")