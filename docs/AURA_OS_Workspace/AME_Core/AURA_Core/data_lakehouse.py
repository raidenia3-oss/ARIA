#!/usr/bin/env python3
"""
data_lakehouse.py - Data Lakehouse para AURA: Sistema de almacenamiento e indexación de datos históricos.
Este módulo implementa un Data Lakehouse que indexa todos los JSON generados por los nodos móviles
(logs, escaneos OSINT, telemetría) y permite consultas avanzadas para correlación de datos.

Características:
- Almacenamiento local de datos en formato JSON y Parquet.
- Indexación full-text y fuzzy matching para búsqueda de dispositivos.
- Integración con el sistema de alertas y correlación de amenazas.
- Generación de informes semanales de amenazas detectadas.
- Soporte para consultas históricas y análisis de patrones.
"""

import os
import sys
import json
import logging
import time
import threading
import argparse
import sqlite3
import hashlib
import glob
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set, Any
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc
from fuzzywuzzy import fuzz, process
from collections import defaultdict
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import networkx as nx
from concurrent.futures import ThreadPoolExecutor
import uuid
import shutil
import zstandard as zstd
import lzma
import bz2
import pickle
import joblib
from pathlib import Path

class DataLakehouse:
    """Data Lakehouse para almacenamiento e indexación de datos históricos de AURA."""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = self._setup_logging()
        self.db_path = config.get("db_path", "/data/data/com.termux/files/home/aura_intel.db")
        self.data_lake_root = config.get("data_lake_root", "/data/data/com.termux/files/home/aura_data_lake")
        self.index_path = config.get("index_path", "/data/data/com.termux/files/home/aura_index.db")
        self.telemetry_path = config.get("telemetry_path", "/data/data/com.termux/files/home/aura_telemetry")
        self.osint_path = config.get("osint_path", "/data/data/com.termux/files/home/aura_osint")
        self.network_path = config.get("network_path", "/data/data/com.termux/files/home/aura_network")
        self.log_path = config.get("log_path", "/data/data/com.termux/files/home/aura_logs")
        self.threat_report_path = config.get("threat_report_path", "/data/data/com.termux/files/home/threat_reports")
        self.max_file_size_mb = config.get("max_file_size_mb", 100)
        self.max_files_per_dir = config.get("max_files_per_dir", 1000)
        self.index_update_interval = config.get("index_update_interval", 3600)  # 1 hora
        self.retention_days = config.get("retention_days", 90)
        self.compression_level = config.get("compression_level", 6)
        self.running = False
        self.shutdown_event = threading.Event()
        self.index_lock = threading.Lock()
        self.data_processor_thread = None
        self.index_updater_thread = None
        self.threat_analyzer_thread = None
        self._initialize_data_lake()

    def _setup_logging(self):
        """Configura el logging para el Data Lakehouse."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/data/data/com.termux/files/home/data_lakehouse.log'),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger("DataLakehouse")
        logger.setLevel(logging.INFO)
        return logger

    def _initialize_data_lake(self):
        """Inicializa la estructura del Data Lakehouse."""
        try:
            # Crear directorios principales si no existen
            os.makedirs(self.data_lake_root, exist_ok=True)
            os.makedirs(self.telemetry_path, exist_ok=True)
            os.makedirs(self.osint_path, exist_ok=True)
            os.makedirs(self.network_path, exist_ok=True)
            os.makedirs(self.log_path, exist_ok=True)
            os.makedirs(self.threat_report_path, exist_ok=True)

            # Inicializar base de datos de índice
            self._initialize_index_database()

            # Crear estructura de directorios por año/mes/día
            self._create_directory_structure()

            self.logger.info("Data Lakehouse inicializado correctamente")
        except Exception as e:
            self.logger.error(f"Error al inicializar Data Lakehouse: {str(e)}")
            raise

    def _initialize_index_database(self):
        """Inicializa la base de datos de índice para búsquedas rápidas."""
        try:
            conn = sqlite3.connect(self.index_path)
            cursor = conn.cursor()

            # Crear tabla devices si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mac TEXT UNIQUE,
                    ip TEXT,
                    vendor TEXT,
                    first_seen DATETIME,
                    last_seen DATETIME,
                    device_type TEXT,
                    os TEXT,
                    manufacturer TEXT,
                    model TEXT,
                    risk_score REAL DEFAULT 0,
                    threat_level TEXT DEFAULT 'unknown',
                    related_events INTEGER DEFAULT 0,
                    notes TEXT,
                    metadata TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Crear tabla device_sightings si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_sightings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id INTEGER,
                    sighting_id TEXT UNIQUE,
                    timestamp DATETIME,
                    node_id TEXT,
                    location TEXT,
                    signal_strength INTEGER,
                    ip_address TEXT,
                    mac_address TEXT,
                    vendor TEXT,
                    device_type TEXT,
                    os TEXT,
                    manufacturer TEXT,
                    model TEXT,
                    risk_score REAL,
                    threat_level TEXT,
                    source_type TEXT,
                    source_path TEXT,
                    processed BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(device_id) REFERENCES devices(id)
                )
            """)

            # Crear tabla device_relationships si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device1_id INTEGER,
                    device2_id INTEGER,
                    relationship_type TEXT,
                    strength REAL,
                    confidence REAL,
                    evidence TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(device1_id) REFERENCES devices(id),
                    FOREIGN KEY(device2_id) REFERENCES devices(id)
                )
            """)

            # Crear tabla threat_intel si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS threat_intel (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    threat_id TEXT UNIQUE,
                    threat_type TEXT,
                    description TEXT,
                    severity TEXT,
                    confidence REAL,
                    first_seen DATETIME,
                    last_seen DATETIME,
                    related_devices INTEGER DEFAULT 0,
                    related_events INTEGER DEFAULT 0,
                    indicators TEXT,
                    references TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Crear tabla threat_relationships si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS threat_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    threat_id TEXT,
                    device_id INTEGER,
                    relationship_type TEXT,
                    strength REAL,
                    confidence REAL,
                    evidence TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(device_id) REFERENCES devices(id)
                )
            """)

            # Crear tabla data_sources si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT UNIQUE,
                    source_type TEXT,
                    path TEXT,
                    file_format TEXT,
                    file_size INTEGER,
                    record_count INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT 0
                )
            """)

            # Crear tabla data_relationships si no existe
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source1_id TEXT,
                    source2_id TEXT,
                    relationship_type TEXT,
                    strength REAL,
                    confidence REAL,
                    evidence TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Crear índices para búsquedas rápidas
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_mac ON devices(mac)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(ip)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_risk_score ON devices(risk_score)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_threat_level ON devices(threat_level)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_device_sightings_device_id ON device_sightings(device_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_device_sightings_timestamp ON device_sightings(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_device_sightings_node_id ON device_sightings(node_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_device_sightings_mac ON device_sightings(mac_address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_device_sightings_ip ON device_sightings(ip_address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_threat_intel_threat_type ON threat_intel(threat_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_threat_intel_severity ON threat_intel(severity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_threat_intel_related_devices ON threat_intel(related_devices)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_sources_source_type ON data_sources(source_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_sources_timestamp ON data_sources(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_sources_path ON data_sources(path)")

            conn.commit()
            conn.close()
            self.logger.info("Base de datos de índice inicializada correctamente")

        except sqlite3.Error as e:
            self.logger.error(f"Error al inicializar base de datos de índice: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error al inicializar base de datos de índice: {str(e)}")
            return False

        return True

    def _create_directory_structure(self):
        """Crea la estructura de directorios por año/mes/día."""
        try:
            # Crear directorios por tipo de dato
            for data_type in ["telemetry", "osint", "network", "logs"]:
                base_path = getattr(self, f"{data_type}_path")
                for year in range(2020, datetime.now().year + 2):  # Años futuros por si acaso
                    year_path = os.path.join(base_path, str(year))
                    os.makedirs(year_path, exist_ok=True)

                    for month in range(1, 13):
                        month_path = os.path.join(year_path, f"{month:02d}")
                        os.makedirs(month_path, exist_ok=True)

                        for day in range(1, 32):  # Días del mes
                            day_path = os.path.join(month_path, f"{day:02d}")
                            os.makedirs(day_path, exist_ok=True)

                            # Crear subdirectorios para diferentes formatos
                            for fmt in ["json", "parquet", "zstd", "lzma"]:
                                fmt_path = os.path.join(day_path, fmt)
                                os.makedirs(fmt_path, exist_ok=True)

        except Exception as e:
            self.logger.error(f"Error al crear estructura de directorios: {str(e)}")
            raise

    def _get_next_file_path(self, data_type: str, file_extension: str = "json") -> str:
        """Obtiene la ruta del próximo archivo para guardar datos."""
        try:
            base_path = getattr(self, f"{data_type}_path")
            today = datetime.now()
            year = today.year
            month = today.month
            day = today.day

            # Construir ruta base
            path = os.path.join(
                base_path,
                str(year),
                f"{month:02d}",
                f"{day:02d}",
                file_extension
            )

            # Encontrar el próximo número de secuencia
            files = glob.glob(f"{path}_*.{file_extension}")
            max_num = 0
            for f in files:
                try:
                    num = int(re.search(r"_(\d+)\.\w+$", f).group(1))
                    if num > max_num:
                        max_num = num
                except:
                    continue

            next_num = max_num + 1
            return f"{path}_{next_num:04d}.{file_extension}"

        except Exception as e:
            self.logger.error(f"Error al obtener ruta de archivo: {str(e)}")
            return ""

    def _rotate_files(self, directory: str, max_files: int = 1000, max_size_mb: int = 100):
        """Rota archivos cuando se superan los límites de tamaño o cantidad."""
        try:
            files = glob.glob(os.path.join(directory, "*"))
            files.sort(key=os.path.getmtime)

            if len(files) <= max_files:
                return

            # Ordenar por tamaño (mayor primero)
            files.sort(key=lambda x: os.path.getsize(x), reverse=True)

            # Eliminar los archivos más grandes hasta que queden max_files
            while len(files) > max_files:
                os.remove(files.pop())
                self.logger.info(f"Archivo eliminado por rotación: {files.pop()}")

        except Exception as e:
            self.logger.error(f"Error al rotar archivos en {directory}: {str(e)}")

    def _compress_file(self, input_path: str, output_path: str, compression: str = "zstd") -> bool:
        """Comprime un archivo usando el método especificado."""
        try:
            if compression == "zstd":
                with open(input_path, 'rb') as f_in:
                    content = f_in.read()
                with zstd.ZstdCompressor(level=self.compression_level) as compressor:
                    with open(output_path, 'wb') as f_out:
                        f_out.write(compressor.compress(content))
            elif compression == "lzma":
                with open(input_path, 'rb') as f_in:
                    with lzma.LZMAFile(output_path, 'wb', preset=self.compression_level) as f_out:
                        shutil.copyfileobj(f_in, f_out)
            elif compression == "bz2":
                with open(input_path, 'rb') as f_in:
                    with bz2.BZ2File(output_path, 'wb') as f_out:
                        f_out.write(f_in.read())
            else:
                # Copiar sin compresión
                shutil.copy2(input_path, output_path)

            # Eliminar el archivo original después de comprimir
            os.remove(input_path)
            return True
        except Exception as e:
            self.logger.error(f"Error al comprimir archivo {input_path}: {str(e)}")
            return False

    def _store_data(self, data_type: str, data: Dict, source_metadata: Optional[Dict] = None) -> str:
        """Almacena datos en el Data Lakehouse."""
        try:
            # Generar ID único para el registro
            record_id = f"rec_{uuid.uuid4().hex[:16]}"
            timestamp = datetime.utcnow().isoformat() + "Z"

            # Añadir metadatos al registro
            if source_metadata:
                data["_metadata"] = {
                    "source_id": source_metadata.get("source_id", record_id),
                    "source_type": source_metadata.get("source_type", data_type),
                    "timestamp": timestamp,
                    "node_id": source_metadata.get("node_id"),
                    "location": source_metadata.get("location"),
                    "file_path": source_metadata.get("file_path")
                }
            else:
                data["_metadata"] = {
                    "source_id": record_id,
                    "source_type": data_type,
                    "timestamp": timestamp
                }

            # Determinar el formato de almacenamiento
            file_extension = "json"
            if data_type in ["telemetry", "network"]:
                file_extension = "parquet"

            # Obtener ruta del archivo
            file_path = self._get_next_file_path(data_type, file_extension)

            # Guardar el registro en el archivo
            if file_extension == "json":
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
            elif file_extension == "parquet":
                # Convertir a DataFrame y guardar como Parquet
                df = pd.DataFrame([data])
                table = pa.Table.from_pandas(df)
                pq.write_table(table, file_path)

            # Registrar la fuente de datos en la base de datos
            self._register_data_source(file_path, data_type, len(data) if isinstance(data, dict) else 1)

            # Rotar archivos si es necesario
            dir_path = os.path.dirname(file_path)
            self._rotate_files(dir_path, self.max_files_per_dir, self.max_file_size_mb)

            # Comprimir el archivo si es grande
            if os.path.getsize(file_path) > self.max_file_size_mb * 1024 * 1024:
                compressed_path = file_path.replace(f".{file_extension}", f".zstd")
                self._compress_file(file_path, compressed_path)
                file_path = compressed_path

            return file_path

        except Exception as e:
            self.logger.error(f"Error al almacenar datos {data_type}: {str(e)}")
            return ""

    def _register_data_source(self, file_path: str, source_type: str, record_count: int) -> bool:
        """Registra una fuente de datos en la base de datos."""
        try:
            conn = sqlite3.connect(self.index_path)
            cursor = conn.cursor()

            # Generar ID único para la fuente
            source_id = hashlib.sha256(file_path.encode()).hexdigest()[:32]

            # Verificar si la fuente ya existe
            cursor.execute("""
                SELECT id FROM data_sources WHERE source_id = ?
            """, (source_id,))

            if cursor.fetchone():
                # Actualizar fuente existente
                cursor.execute("""
                    UPDATE data_sources
                    SET path = ?, file_format = ?, record_count = ?, timestamp = CURRENT_TIMESTAMP,
                        processed = 0
                    WHERE source_id = ?
                """, (file_path, os.path.splitext(file_path)[1][1:], record_count, source_id))
            else:
                # Insertar nueva fuente
                cursor.execute("""
                    INSERT INTO data_sources (
                        source_id, source_type, path, file_format, record_count, timestamp
                    ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (source_id, source_type, file_path, os.path.splitext(file_path)[1][1:], record_count))

            conn.commit()
            conn.close()
            return True

        except sqlite3.Error as e:
            self.logger.error(f"Error al registrar fuente de datos: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error al registrar fuente de datos: {str(e)}")
            return False

    def _index_device_sighting(self, device_data: Dict) -> bool:
        """Índica una aparición de dispositivo en la base de datos."""
        try:
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                # Extraer información del dispositivo
                mac = device_data.get("mac", "").upper()
                ip = device_data.get("ip")
                vendor = device_data.get("vendor", "Unknown")
                device_type = device_data.get("device_type")
                os_info = device_data.get("os")
                manufacturer = device_data.get("manufacturer")
                model = device_data.get("model")
                timestamp = device_data.get("timestamp")
                node_id = device_data.get("node_id")
                source_path = device_data.get("source_path")
                source_type = device_data.get("source_type", "network")

                # Verificar si el dispositivo ya existe en la base de datos
                cursor.execute("""
                    SELECT id FROM devices WHERE mac = ?
                """, (mac,))

                device_result = cursor.fetchone()
                device_id = device_result[0] if device_result else None

                # Crear o actualizar el dispositivo
                if not device_id:
                    # Insertar nuevo dispositivo
                    cursor.execute("""
                        INSERT INTO devices (
                            mac, ip, vendor, first_seen, last_seen, device_type, os,
                            manufacturer, model, risk_score, threat_level, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (
                        mac, ip, vendor, timestamp, timestamp, device_type, os_info,
                        manufacturer, model, 0.0, "unknown"
                    ))
                    device_id = cursor.lastrowid
                else:
                    # Actualizar dispositivo existente
                    cursor.execute("""
                        UPDATE devices
                        SET ip = ?, vendor = ?, last_seen = CURRENT_TIMESTAMP, device_type = ?,
                            os = ?, manufacturer = ?, model = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (ip, vendor, device_type, os_info, manufacturer, model, device_id))

                # Generar ID único para el avistamiento
                sighting_id = f"sight_{uuid.uuid4().hex[:16]}"

                # Insertar avistamiento del dispositivo
                cursor.execute("""
                    INSERT INTO device_sightings (
                        device_id, sighting_id, timestamp, node_id, location, signal_strength,
                        ip_address, mac_address, vendor, device_type, os, manufacturer, model,
                        risk_score, threat_level, source_type, source_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    device_id, sighting_id, timestamp, node_id, device_data.get("location"),
                    device_data.get("signal_strength"), ip, mac, vendor, device_type, os_info,
                    manufacturer, model, device_data.get("risk_score", 0.0),
                    device_data.get("threat_level", "unknown"), source_type, source_path
                ))

                # Actualizar contador de avistamientos del dispositivo
                cursor.execute("""
                    UPDATE devices
                    SET related_events = related_events + 1
                    WHERE id = ?
                """, (device_id,))

                conn.commit()
                conn.close()
                return True

        except sqlite3.Error as e:
            self.logger.error(f"Error al indexar avistamiento de dispositivo: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Error al indexar avistamiento de dispositivo: {str(e)}")
            return False

    def _find_similar_devices(self, mac: str, threshold: int = 80) -> List[Dict]:
        """Encuentra dispositivos similares usando fuzzy matching."""
        try:
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                # Obtener todos los dispositivos con MACs similares
                cursor.execute("""
                    SELECT id, mac, ip, vendor, first_seen, last_seen, related_events
                    FROM devices
                    WHERE mac != ?
                """, (mac,))

                devices = cursor.fetchall()

                similar_devices = []
                for device in devices:
                    device_mac = device[1]
                    similarity = fuzz.ratio(mac, device_mac)
                    if similarity >= threshold:
                        similar_devices.append({
                            "id": device[0],
                            "mac": device[1],
                            "ip": device[2],
                            "vendor": device[3],
                            "first_seen": device[4],
                            "last_seen": device[5],
                            "related_events": device[6],
                            "similarity": similarity
                        })

                # Ordenar por similitud (de mayor a menor)
                similar_devices.sort(key=lambda x: x["similarity"], reverse=True)

                return similar_devices

        except sqlite3.Error as e:
            self.logger.error(f"Error al buscar dispositivos similares: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error al buscar dispositivos similares: {str(e)}")
            return []

    def _analyze_device_behavior(self, device_id: int) -> Dict:
        """Analiza el comportamiento de un dispositivo basado en sus avistamientos."""
        try:
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                # Obtener información del dispositivo
                cursor.execute("""
                    SELECT mac, ip, vendor, first_seen, last_seen, related_events, risk_score, threat_level
                    FROM devices
                    WHERE id = ?
                """, (device_id,))
                device = cursor.fetchone()

                if not device:
                    return {"error": "Device not found"}

                device_info = {
                    "id": device_id,
                    "mac": device[0],
                    "ip": device[1],
                    "vendor": device[2],
                    "first_seen": device[3],
                    "last_seen": device[4],
                    "related_events": device[5],
                    "risk_score": device[6],
                    "threat_level": device[7],
                    "behavior_analysis": {}
                }

                # Obtener todos los avistamientos del dispositivo
                cursor.execute("""
                    SELECT timestamp, node_id, location, signal_strength, ip_address, mac_address,
                           vendor, device_type, os, manufacturer, model, risk_score, threat_level, source_type
                    FROM device_sightings
                    WHERE device_id = ?
                    ORDER BY timestamp
                """, (device_id,))
                sightings = cursor.fetchall()

                if not sightings:
                    return device_info

                # Analizar patrones temporales
                timestamps = [datetime.strptime(sighting[0], "%Y-%m-%dT%H:%M:%SZ") for sighting in sightings]
                time_diffs = [(timestamps[i+1] - timestamps[i]).total_seconds() for i in range(len(timestamps)-1)]

                # Calcular estadísticas temporales
                avg_time_between = np.mean(time_diffs) if time_diffs else 0
                std_time_between = np.std(time_diffs) if time_diffs else 0

                # Analizar cambios en IP y MAC
                ip_changes = sum(1 for i in range(1, len(sightings)) if sightings[i][5] != sightings[i-1][5])
                mac_changes = sum(1 for i in range(1, len(sightings)) if sightings[i][6] != sightings[i-1][6])

                # Analizar cambios en vendor y device_type
                vendor_changes = sum(1 for i in range(1, len(sightings)) if sightings[i][7] != sightings[i-1][7])
                device_type_changes = sum(1 for i in range(1, len(sightings)) if sightings[i][8] != sightings[i-1][8])

                # Analizar patrones de riesgo
                risk_scores = [sighting[11] for sighting in sightings]
                avg_risk = np.mean(risk_scores) if risk_scores else 0
                max_risk = max(risk_scores) if risk_scores else 0

                # Analizar amenazas detectadas
                threat_levels = [sighting[12] for sighting in sightings]
                threat_counts = defaultdict(int)
                for level in threat_levels:
                    if level != "unknown":
                        threat_counts[level] += 1

                # Determinar nivel de amenaza general
                if threat_counts:
                    threat_level = max(threat_counts.items(), key=lambda x: ("high", "medium", "low").index(x[0]))[0]
                else:
                    threat_level = "unknown"

                # Calcular puntuación de comportamiento
                behavior_score = 0

                # Penalizar cambios frecuentes en IP/MAC
                if ip_changes > 0:
                    behavior_score += min(20, ip_changes * 5)
                if mac_changes > 0:
                    behavior_score += min(20, mac_changes * 5)

                # Penalizar cambios en vendor/device_type
                if vendor_changes > 0:
                    behavior_score += min(15, vendor_changes * 5)
                if device_type_changes > 0:
                    behavior_score += min(15, device_type_changes * 5)

                # Penalizar riesgo alto
                if max_risk > 0.7:
                    behavior_score += min(30, (max_risk - 0.7) * 100)

                # Penalizar actividad irregular (muy frecuente o muy espaciada)
                if avg_time_between < 300:  # Menos de 5 minutos entre avistamientos
                    behavior_score += min(15, (300 - avg_time_between) / 300 * 100)
                elif avg_time_between > 86400:  # Más de 24 horas entre avistamientos
                    behavior_score += min(10, avg_time_between / 86400 * 100)

                # Ajustar puntuación de riesgo del dispositivo
                new_risk_score = min(100, max(0, device_info["risk_score"] + behavior_score))
                device_info["risk_score"] = new_risk_score

                # Determinar nuevo nivel de amenaza
                if new_risk_score >= 80:
                    device_info["threat_level"] = "critical"
                elif new_risk_score >= 50:
                    device_info["threat_level"] = "high"
                elif new_risk_score >= 30:
                    device_info["threat_level"] = "medium"
                else:
                    device_info["threat_level"] = "low"

                # Añadir análisis de comportamiento
                device_info["behavior_analysis"] = {
                    "time_between_sightings": {
                        "average_seconds": avg_time_between,
                        "standard_deviation": std_time_between,
                        "min_seconds": min(time_diffs) if time_diffs else 0,
                        "max_seconds": max(time_diffs) if time_diffs else 0
                    },
                    "ip_changes": ip_changes,
                    "mac_changes": mac_changes,
                    "vendor_changes": vendor_changes,
                    "device_type_changes": device_type_changes,
                    "risk_scores": {
                        "average": avg_risk,
                        "maximum": max_risk,
                        "distribution": threat_counts
                    },
                    "threat_level": threat_level,
                    "behavior_score": behavior_score,
                    "total_sightings": len(sightings),
                    "time_range_days": (timestamps[-1] - timestamps[0]).days if len(timestamps) > 1 else 0,
                    "nodes_seen": len(set(sighting[1] for sighting in sightings)),
                    "locations_seen": len(set(sighting[2] for sighting in sightings if sighting[2]))
                }

                return device_info

        except sqlite3.Error as e:
            self.logger.error(f"Error al analizar comportamiento de dispositivo: {str(e)}")
            return {"error": str(e)}
        except Exception as e:
            self.logger.error(f"Error al analizar comportamiento de dispositivo: {str(e)}")
            return {"error": str(e)}

    def _find_related_devices(self, device_id: int, threshold: float = 0.7) -> List[Dict]:
        """Encuentra dispositivos relacionados con uno existente."""
        try:
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                # Obtener información del dispositivo de referencia
                cursor.execute("""
                    SELECT mac, ip, vendor, device_type, os, manufacturer, model
                    FROM devices
                    WHERE id = ?
                """, (device_id,))
                ref_device = cursor.fetchone()

                if not ref_device:
                    return []

                ref_mac = ref_device[0]
                ref_ip = ref_device[1]
                ref_vendor = ref_device[2]
                ref_device_type = ref_device[3]
                ref_os = ref_device[4]
                ref_manufacturer = ref_device[5]
                ref_model = ref_device[6]

                # Obtener todos los avistamientos del dispositivo de referencia
                cursor.execute("""
                    SELECT ip_address, mac_address, vendor, device_type, os, manufacturer, model
                    FROM device_sightings
                    WHERE device_id = ?
                """, (device_id,))
                ref_sightings = cursor.fetchall()

                if not ref_sightings:
                    return []

                # Crear un vector de características para el dispositivo de referencia
                ref_features = self._create_device_feature_vector(ref_sightings)

                # Obtener todos los otros dispositivos
                cursor.execute("""
                    SELECT id, mac, ip, vendor, device_type, os, manufacturer, model
                    FROM devices
                    WHERE id != ?
                """, (device_id,))
                other_devices = cursor.fetchall()

                related_devices = []
                for device in other_devices:
                    device_id, device_mac, device_ip, device_vendor, device_type, device_os, device_manufacturer, device_model = device

                    # Obtener avistamientos del dispositivo candidato
                    cursor.execute("""
                        SELECT ip_address, mac_address, vendor, device_type, os, manufacturer, model
                        FROM device_sightings
                        WHERE device_id = ?
                    """, (device_id,))
                    candidate_sightings = cursor.fetchall()

                    if not candidate_sightings:
                        continue

                    # Crear vector de características para el dispositivo candidato
                    candidate_features = self._create_device_feature_vector(candidate_sightings)

                    # Calcular similitud usando cosine similarity
                    similarity = self._calculate_device_similarity(ref_features, candidate_features)

                    if similarity >= threshold:
                        related_devices.append({
                            "device_id": device_id,
                            "mac": device_mac,
                            "ip": device_ip,
                            "vendor": device_vendor,
                            "device_type": device_type,
                            "os": device_os,
                            "manufacturer": device_manufacturer,
                            "model": device_model,
                            "similarity": similarity,
                            "common_features": self._find_common_features(ref_sightings, candidate_sightings)
                        })

                # Ordenar por similitud (de mayor a menor)
                related_devices.sort(key=lambda x: x["similarity"], reverse=True)

                return related_devices

        except sqlite3.Error as e:
            self.logger.error(f"Error al encontrar dispositivos relacionados: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error al encontrar dispositivos relacionados: {str(e)}")
            return []

    def _create_device_feature_vector(self, sightings: List[Tuple]) -> Dict:
        """Crea un vector de características para un dispositivo basado en sus avistamientos."""
        features = {
            "mac_patterns": [],
            "ip_patterns": [],
            "vendor": set(),
            "device_type": set(),
            "os": set(),
            "manufacturer": set(),
            "model": set(),
            "time_patterns": [],
            "location_patterns": [],
            "signal_patterns": []
        }

        for sighting in sightings:
            # Extraer patrones de MAC (primeros 3 bytes suelen ser del fabricante)
            mac = sighting[1]
            if mac:
                mac_pattern = mac[:8]  # Primeros 8 caracteres (primeros 3 bytes MAC)
                features["mac_patterns"].append(mac_pattern)

            # Extraer patrones de IP (primeros octetos)
            ip = sighting[0]
            if ip:
                ip_parts = ip.split('.')
                if len(ip_parts) == 4:
                    ip_pattern = f"{ip_parts[0]}.{ip_parts[1]}"  # Primeros dos octetos
                    features["ip_patterns"].append(ip_pattern)

            # Añadir información de vendor
            vendor = sighting[2]
            if vendor:
                features["vendor"].add(vendor.lower())

            # Añadir información de device_type
            device_type = sighting[3]
            if device_type:
                features["device_type"].add(device_type.lower())

            # Añadir información de OS
            os_info = sighting[4]
            if os_info:
                features["os"].add(os_info.lower())

            # Añadir información de manufacturer
            manufacturer = sighting[5]
            if manufacturer:
                features["manufacturer"].add(manufacturer.lower())

            # Añadir información de model
            model = sighting[6]
            if model:
                features["model"].add(model.lower())

            # Añadir patrones temporales (hora del día)
            timestamp = sighting[0]  # Asumiendo que el primer elemento es la marca de tiempo
            try:
                dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
                hour = dt.hour
                features["time_patterns"].append(hour)
            except:
                pass

            # Añadir patrones de ubicación (si disponible)
            location = sighting[2]  # Asumiendo que el tercer elemento es la ubicación
            if location:
                features["location_patterns"].append(location.lower())

            # Añadir patrones de señal
            signal = sighting[3]  # Asumiendo que el cuarto elemento es la señal
            if signal:
                features["signal_patterns"].append(signal)

        # Convertir sets a listas para serialización
        for key in ["vendor", "device_type", "os", "manufacturer", "model"]:
            features[key] = list(features[key])

        return features

    def _calculate_device_similarity(self, ref_features: Dict, candidate_features: Dict) -> float:
        """Calcula la similitud entre dos dispositivos usando sus vectores de características."""
        try:
            # Comparar patrones de MAC
            mac_similarity = self._calculate_set_similarity(ref_features["mac_patterns"], candidate_features["mac_patterns"])

            # Comparar patrones de IP
            ip_similarity = self._calculate_set_similarity(ref_features["ip_patterns"], candidate_features["ip_patterns"])

            # Comparar vendors
            vendor_similarity = self._calculate_set_similarity(ref_features["vendor"], candidate_features["vendor"])

            # Comparar device_types
            device_type_similarity = self._calculate_set_similarity(ref_features["device_type"], candidate_features["device_type"])

            # Comparar OS
            os_similarity = self._calculate_set_similarity(ref_features["os"], candidate_features["os"])

            # Comparar manufacturers
            manufacturer_similarity = self._calculate_set_similarity(ref_features["manufacturer"], candidate_features["manufacturer"])

            # Comparar models
            model_similarity = self._calculate_set_similarity(ref_features["model"], candidate_features["model"])

            # Comparar patrones temporales (usando distribución de horas)
            time_similarity = self._calculate_time_pattern_similarity(ref_features["time_patterns"], candidate_features["time_patterns"])

            # Comparar patrones de señal
            signal_similarity = self._calculate_list_similarity(ref_features["signal_patterns"], candidate_features["signal_patterns"])

            # Ponderar las similitudes
            total_similarity = (
                0.2 * mac_similarity +
                0.15 * ip_similarity +
                0.1 * vendor_similarity +
                0.1 * device_type_similarity +
                0.1 * os_similarity +
                0.1 * manufacturer_similarity +
                0.1 * model_similarity +
                0.15 * time_similarity +
                0.05 * signal_similarity
            )

            return total_similarity

        except Exception as e:
            self.logger.error(f"Error al calcular similitud de dispositivos: {str(e)}")
            return 0.0

    def _calculate_set_similarity(self, set1: List, set2: List) -> float:
        """Calcula la similitud entre dos conjuntos usando Jaccard similarity."""
        if not set1 or not set2:
            return 0.0

        intersection = len(set(set1) & set(set2))
        union = len(set(set1) | set(set2))

        if union == 0:
            return 0.0

        return intersection / union

    def _calculate_list_similarity(self, list1: List, list2: List) -> float:
        """Calcula la similitud entre dos listas usando cosine similarity."""
        if not list1 or not list2:
            return 0.0

        # Crear vectores de características simples
        vectorizer = TfidfVectorizer()
        vectors = vectorizer.fit_transform([" ".join(map(str, list1)), " ".join(map(str, list2))])
        return cosine_similarity(vectors[0:1], vectors[1:2])[0][0]

    def _calculate_time_pattern_similarity(self, times1: List, times2: List) -> float:
        """Calcula la similitud entre patrones temporales."""
        if not times1 or not times2:
            return 0.0

        # Crear histogramas de horas
        hist1 = np.bincount([t % 24 for t in times1], minlength=24)
        hist2 = np.bincount([t % 24 for t in times2], minlength=24)

        # Normalizar histogramas
        hist1 = hist1 / (len(times1) + 1e-10)
        hist2 = hist2 / (len(times2) + 1e-10)

        # Calcular similitud usando cosine similarity
        return cosine_similarity([hist1], [hist2])[0][0]

    def _find_common_features(self, ref_sightings: List[Tuple], candidate_sightings: List[Tuple]) -> Dict:
        """Encuentra características comunes entre dos conjuntos de avistamientos."""
        common_features = {
            "mac_patterns": set(),
            "ip_patterns": set(),
            "vendors": set(),
            "device_types": set(),
            "oses": set(),
            "manufacturers": set(),
            "models": set(),
            "common_timestamps": 0,
            "common_locations": 0
        }

        # Extraer patrones de MAC
        ref_macs = [sighting[1][:8] for sighting in ref_sightings if sighting[1]]
        candidate_macs = [sighting[1][:8] for sighting in candidate_sightings if sighting[1]]
        common_features["mac_patterns"] = set(ref_macs) & set(candidate_macs)

        # Extraer patrones de IP
        ref_ips = [f"{sighting[0].split('.')[0]}.{sighting[0].split('.')[1]}" for sighting in ref_sightings if sighting[0]]
        candidate_ips = [f"{sighting[0].split('.')[0]}.{sighting[0].split('.')[1]}" for sighting in candidate_sightings if sighting[0]]
        common_features["ip_patterns"] = set(ref_ips) & set(candidate_ips)

        # Extraer vendors
        ref_vendors = [sighting[2].lower() for sighting in ref_sightings if sighting[2]]
        candidate_vendors = [sighting[2].lower() for sighting in candidate_sightings if sighting[2]]
        common_features["vendors"] = set(ref_vendors) & set(candidate_vendors)

        # Extraer device_types
        ref_device_types = [sighting[3].lower() for sighting in ref_sightings if sighting[3]]
        candidate_device_types = [sighting[3].lower() for sighting in candidate_sightings if sighting[3]]
        common_features["device_types"] = set(ref_device_types) & set(candidate_device_types)

        # Extraer OS
        ref_oses = [sighting[4].lower() for sighting in ref_sightings if sighting[4]]
        candidate_oses = [sighting[4].lower() for sighting in candidate_sightings if sighting[4]]
        common_features["oses"] = set(ref_oses) & set(candidate_oses)

        # Extraer manufacturers
        ref_manufacturers = [sighting[5].lower() for sighting in ref_sightings if sighting[5]]
        candidate_manufacturers = [sighting[5].lower() for sighting in candidate_sightings if sighting[5]]
        common_features["manufacturers"] = set(ref_manufacturers) & set(candidate_manufacturers)

        # Extraer models
        ref_models = [sighting[6].lower() for sighting in ref_sightings if sighting[6]]
        candidate_models = [sighting[6].lower() for sighting in candidate_sightings if sighting[6]]
        common_features["models"] = set(ref_models) & set(candidate_models)

        # Contar timestamps comunes (simplificado)
        ref_timestamps = [sighting[0] for sighting in ref_sightings]
        candidate_timestamps = [sighting[0] for sighting in candidate_sightings]
        common_features["common_timestamps"] = len(set(ref_timestamps) & set(candidate_timestamps))

        # Contar ubicaciones comunes (simplificado)
        ref_locations = [sighting[2].lower() for sighting in ref_sightings if sighting[2]]
        candidate_locations = [sighting[2].lower() for sighting in candidate_sightings if sighting[2]]
        common_features["common_locations"] = len(set(ref_locations) & set(candidate_locations))

        return common_features

    def _generate_threat_report(self, start_date: datetime, end_date: datetime) -> Dict:
        """Genera un informe de amenazas basado en los datos históricos."""
        try:
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                report = {
                    "report_id": f"threat_report_{uuid.uuid4().hex[:16]}",
                    "title": f"AURA Threat Report: {start_date.date()} to {end_date.date()}",
                    "period": {
                        "start_date": start_date.isoformat() + "Z",
                        "end_date": end_date.isoformat() + "Z",
                        "duration_days": (end_date - start_date).days
                    },
                    "summary": {},
                    "devices": [],
                    "threats": [],
                    "device_relationships": [],
                    "recommendations": [],
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    "data_sources": []
                }

                # 1. Obtener estadísticas generales
                cursor.execute("""
                    SELECT COUNT(*) FROM devices
                """)
                report["summary"]["total_devices"] = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT COUNT(*) FROM device_sightings
                    WHERE timestamp BETWEEN ? AND ?
                """, (start_date.isoformat() + "Z", end_date.isoformat() + "Z"))
                report["summary"]["total_sightings"] = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT COUNT(DISTINCT device_id) FROM device_sightings
                    WHERE timestamp BETWEEN ? AND ?
                """, (start_date.isoformat() + "Z", end_date.isoformat() + "Z"))
                report["summary"]["active_devices"] = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT COUNT(*) FROM threat_intel
                    WHERE first_seen BETWEEN ? AND ?
                """, (start_date.isoformat() + "Z", end_date.isoformat() + "Z"))
                report["summary"]["new_threats"] = cursor.fetchone()[0]

                # 2. Obtener dispositivos con mayor actividad
                cursor.execute("""
                    SELECT id, mac, ip, vendor, first_seen, last_seen, related_events, risk_score, threat_level
                    FROM devices
                    WHERE related_events > 0
                    ORDER BY related_events DESC, risk_score DESC
                    LIMIT 20
                """)
                devices = cursor.fetchall()

                for device in devices:
                    device_info = {
                        "device_id": device[0],
                        "mac": device[1],
                        "ip": device[2],
                        "vendor": device[3],
                        "first_seen": device[4],
                        "last_seen": device[5],
                        "related_events": device[6],
                        "risk_score": device[7],
                        "threat_level": device[8],
                        "behavior_analysis": self._analyze_device_behavior(device[0])
                    }
                    report["devices"].append(device_info)

                # 3. Obtener amenazas más significativas
                cursor.execute("""
                    SELECT id, threat_id, threat_type, description, severity, confidence,
                           first_seen, last_seen, related_devices, related_events
                    FROM threat_intel
                    WHERE first_seen BETWEEN ? AND ?
                    ORDER BY severity DESC, confidence DESC, related_devices DESC
                    LIMIT 10
                """, (start_date.isoformat() + "Z", end_date.isoformat() + "Z"))
                threats = cursor.fetchall()

                for threat in threats:
                    threat_info = {
                        "threat_id": threat[1],
                        "threat_type": threat[2],
                        "description": threat[3],
                        "severity": threat[4],
                        "confidence": threat[5],
                        "first_seen": threat[6],
                        "last_seen": threat[7],
                        "related_devices": threat[8],
                        "related_events": threat[9],
                        "devices": self._get_threat_related_devices(threat[1])
                    }
                    report["threats"].append(threat_info)

                # 4. Obtener relaciones entre dispositivos
                cursor.execute("""
                    SELECT d1.id, d1.mac, d2.id, d2.mac, relationship_type, strength, confidence
                    FROM device_relationships dr
                    JOIN devices d1 ON dr.device1_id = d1.id
                    JOIN devices d2 ON dr.device2_id = d2.id
                    WHERE dr.timestamp BETWEEN ? AND ?
                    ORDER BY strength DESC, confidence DESC
                    LIMIT 20
                """, (start_date.isoformat() + "Z", end_date.isoformat() + "Z"))
                relationships = cursor.fetchall()

                for rel in relationships:
                    report["device_relationships"].append({
                        "device1_id": rel[0],
                        "device1_mac": rel[1],
                        "device2_id": rel[2],
                        "device2_mac": rel[3],
                        "relationship_type": rel[4],
                        "strength": rel[5],
                        "confidence": rel[6]
                    })

                # 5. Generar recomendaciones
                self._generate_recommendations(report, start_date, end_date)

                # 6. Obtener fuentes de datos utilizadas
                cursor.execute("""
                    SELECT source_id, source_type, path, file_format, record_count, timestamp
                    FROM data_sources
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp DESC
                    LIMIT 50
                """, (start_date.isoformat() + "Z", end_date.isoformat() + "Z"))
                data_sources = cursor.fetchall()

                for source in data_sources:
                    report["data_sources"].append({
                        "source_id": source[0],
                        "source_type": source[1],
                        "path": source[2],
                        "file_format": source[3],
                        "record_count": source[4],
                        "timestamp": source[5]
                    })

                # 7. Calcular métricas adicionales
                self._calculate_report_metrics(report, start_date, end_date)

                return report

        except sqlite3.Error as e:
            self.logger.error(f"Error al generar informe de amenazas: {str(e)}")
            return {"error": str(e)}
        except Exception as e:
            self.logger.error(f"Error al generar informe de amenazas: {str(e)}")
            return {"error": str(e)}

    def _get_threat_related_devices(self, threat_id: str) -> List[Dict]:
        """Obtiene dispositivos relacionados con una amenaza específica."""
        try:
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                devices = []
                cursor.execute("""
                    SELECT d.id, d.mac, d.ip, d.vendor, d.risk_score, d.threat_level, tr.strength, tr.confidence
                    FROM threat_relationships tr
                    JOIN devices d ON tr.device_id = d.id
                    WHERE tr.threat_id = ?
                    ORDER BY tr.strength DESC, tr.confidence DESC
                """, (threat_id,))

                for row in cursor.fetchall():
                    devices.append({
                        "device_id": row[0],
                        "mac": row[1],
                        "ip": row[2],
                        "vendor": row[3],
                        "risk_score": row[4],
                        "threat_level": row[5],
                        "relationship_strength": row[6],
                        "confidence": row[7]
                    })

                return devices

        except sqlite3.Error as e:
            self.logger.error(f"Error al obtener dispositivos relacionados con amenaza: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error al obtener dispositivos relacionados con amenaza: {str(e)}")
            return []

    def _generate_recommendations(self, report: Dict, start_date: datetime, end_date: datetime):
        """Genera recomendaciones basadas en el análisis de amenazas."""
        try:
            recommendations = []

            # 1. Dispositivos con alto riesgo
            high_risk_devices = [d for d in report["devices"] if d["threat_level"] in ["high", "critical"]]
            if high_risk_devices:
                recommendations.append({
                    "id": "high_risk_devices",
                    "title": "Dispositivos de Alto Riesgo Detectados",
                    "description": f"Se han detectado {len(high_risk_devices)} dispositivos con niveles de amenaza altos o críticos.",
                    "severity": "high",
                    "devices": [d["mac"] for d in high_risk_devices],
                    "recommendation": (
                        "Investigar estos dispositivos inmediatamente. "
                        "Considerar bloquear el acceso a la red y realizar un análisis forense "
                        "para determinar si están comprometidos."
                    ),
                    "actions": [
                        "Bloquear dispositivos en firewalls y routers",
                        "Realizar análisis forense en dispositivos seleccionados",
                        "Notificar al equipo de seguridad",
                        "Revisar logs de red para actividad sospechosa"
                    ]
                })

            # 2. Dispositivos con comportamiento anómalo
            anomalous_devices = [d for d in report["devices"] if d["behavior_analysis"]["behavior_score"] > 30]
            if anomalous_devices:
                recommendations.append({
                    "id": "anomalous_behavior",
                    "title": "Comportamiento Anómalo Detectado",
                    "description": f"Se han detectado {len(anomalous_devices)} dispositivos con comportamiento anómalo.",
                    "severity": "medium",
                    "devices": [d["mac"] for d in anomalous_devices],
                    "recommendation": (
                        "Analizar el comportamiento de estos dispositivos para identificar "
                        "patrones de actividad sospechosa o maliciosa."
                    ),
                    "actions": [
                        "Revisar históricos de avistamientos",
                        "Analizar patrones temporales y geográficos",
                        "Correlacionar con otras amenazas conocidas",
                        "Considerar cuarentena temporal"
                    ]
                })

            # 3. Nuevas amenazas detectadas
            new_threats = [t for t in report["threats"] if t["severity"] in ["high", "critical"]]
            if new_threats:
                recommendations.append({
                    "id": "new_threats",
                    "title": "Nuevas Amenazas Detectadas",
                    "description": f"Se han identificado {len(new_threats)} nuevas amenazas significativas.",
                    "severity": "high",
                    "threats": [t["threat_id"] for t in new_threats],
                    "recommendation": (
                        "Evaluar inmediatamente el impacto de estas amenazas y "
                        "implementar contramedidas según corresponda."
                    ),
                    "actions": [
                        "Actualizar sistemas de detección de amenazas",
                        "Implementar reglas de prevención en firewalls",
                        "Notificar a equipos de respuesta a incidentes",
                        "Revisar vulnerabilidades relacionadas"
                    ]
                })

            # 4. Dispositivos con múltiples avistamientos
            frequent_devices = [d for d in report["devices"] if d["related_events"] > 10]
            if frequent_devices:
                recommendations.append({
                    "id": "frequent_devices",
                    "title": "Dispositivos con Alta Frecuencia de Avistamientos",
                    "description": f"Se han detectado {len(frequent_devices)} dispositivos con alta frecuencia de actividad.",
                    "severity": "medium",
                    "devices": [d["mac"] for d in frequent_devices],
                    "recommendation": (
                        "Analizar si esta actividad es normal para el entorno o podría indicar "
                        "comportamiento sospechoso o malicioso."
                    ),
                    "actions": [
                        "Verificar si los dispositivos pertenecen a usuarios autorizados",
                        "Analizar patrones de movimiento y acceso a recursos",
                        "Correlacionar con otras amenazas conocidas",
                        "Considerar implementar políticas de acceso más restrictivas"
                    ]
                })

            # 5. Relaciones entre dispositivos sospechosos
            suspicious_relationships = [r for r in report["device_relationships"] if r["relationship_type"] in ["potential_communication", "shared_behavior"]]
            if suspicious_relationships:
                recommendations.append({
                    "id": "suspicious_relationships",
                    "title": "Relaciones Sospechosas entre Dispositivos",
                    "description": f"Se han detectado {len(suspicious_relationships)} relaciones potencialmente sospechosas entre dispositivos.",
                    "severity": "medium",
                    "relationships": [
                        f"{r['device1_mac']} <-> {r['device2_mac']} ({r['relationship_type']})"
                        for r in suspicious_relationships
                    ],
                    "recommendation": (
                        "Investigar estas relaciones para determinar si podrían indicar "
                        "comunicación no autorizada o comportamiento coordinado entre dispositivos."
                    ),
                    "actions": [
                        "Analizar tráfico de red entre dispositivos relacionados",
                        "Revisar logs de comunicación",
                        "Considerar aislamiento temporal de dispositivos",
                        "Notificar al equipo de seguridad"
                    ]
                })

            # 6. Dispositivos sin identificación clara
            unknown_devices = [d for d in report["devices"] if d["vendor"] == "Unknown" or d["manufacturer"] == "Unknown"]
            if unknown_devices:
                recommendations.append({
                    "id": "unknown_devices",
                    "title": "Dispositivos sin Identificación Clara",
                    "description": f"Se han detectado {len(unknown_devices)} dispositivos con información de fabricante desconocida.",
                    "severity": "medium",
                    "devices": [d["mac"] for d in unknown_devices],
                    "recommendation": (
                        "Intentar identificar estos dispositivos mediante análisis forense o "
                        "consultar bases de datos de fabricantes conocidos."
                    ),
                    "actions": [
                        "Realizar análisis forense en dispositivos seleccionados",
                        "Consultar bases de datos de OUI (Organizationally Unique Identifier)",
                        "Intentar determinar el tipo de dispositivo mediante análisis de tráfico",
                        "Considerar bloqueo preventivo si no pueden ser identificados"
                    ]
                })

            # Añadir recomendaciones al informe
            report["recommendations"] = recommendations

        except Exception as e:
            self.logger.error(f"Error al generar recomendaciones: {str(e)}")

    def _calculate_report_metrics(self, report: Dict, start_date: datetime, end_date: datetime):
        """Calcula métricas adicionales para el informe de amenazas."""
        try:
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                # 1. Tendencias de actividad
                cursor.execute("""
                    SELECT
                        strftime('%Y-%m-%d', timestamp) as day,
                        COUNT(*) as sightings,
                        COUNT(DISTINCT device_id) as unique_devices
                    FROM device_sightings
                    WHERE timestamp BETWEEN ? AND ?
                    GROUP BY day
                    ORDER BY day
                """, (start_date.isoformat() + "Z", end_date.isoformat() + "Z"))
                activity_trends = cursor.fetchall()

                report["summary"]["activity_trends"] = {
                    "daily_sightings": [{"date": row[0], "count": row[1]} for row in activity_trends],
                    "daily_unique_devices": [{"date": row[0], "count": row[2]} for row in activity_trends]
                }

                # 2. Distribución de niveles de amenaza
                cursor.execute("""
                    SELECT threat_level, COUNT(*) as count
                    FROM devices
                    WHERE related_events > 0
                    GROUP BY threat_level
                    ORDER BY threat_level
                """)
                threat_level_distribution = cursor.fetchall()

                report["summary"]["threat_level_distribution"] = {
                    level: count for level, count in threat_level_distribution
                }

                # 3. Distribución de tipos de dispositivos
                cursor.execute("""
                    SELECT device_type, COUNT(*) as count
                    FROM devices
                    WHERE device_type IS NOT NULL AND device_type != ''
                    GROUP BY device_type
                    ORDER BY count DESC
                    LIMIT 10
                """)
                device_type_distribution = cursor.fetchall()

                report["summary"]["device_type_distribution"] = {
                    device_type: count for device_type, count in device_type_distribution
                }

                # 4. Dispositivos con mayor riesgo
                cursor.execute("""
                    SELECT mac, ip, vendor, risk_score, threat_level
                    FROM devices
                    WHERE risk_score > 50
                    ORDER BY risk_score DESC
                    LIMIT 5
                """)
                high_risk_devices = cursor.fetchall()

                report["summary"]["high_risk_devices"] = [
                    {
                        "mac": row[0],
                        "ip": row[1],
                        "vendor": row[2],
                        "risk_score": row[3],
                        "threat_level": row[4]
                    }
                    for row in high_risk_devices
                ]

                # 5. Amenazas más frecuentes
                cursor.execute("""
                    SELECT threat_type, COUNT(*) as count
                    FROM threat_intel
                    WHERE first_seen BETWEEN ? AND ?
                    GROUP BY threat_type
                    ORDER BY count DESC
                    LIMIT 10
                """, (start_date.isoformat() + "Z", end_date.isoformat() + "Z"))
                threat_type_distribution = cursor.fetchall()

                report["summary"]["threat_type_distribution"] = {
                    threat_type: count for threat_type, count in threat_type_distribution
                }

        except sqlite3.Error as e:
            self.logger.error(f"Error al calcular métricas del informe: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error al calcular métricas del informe: {str(e)}")

    def _save_threat_report(self, report: Dict) -> str:
        """Guarda un informe de amenazas en el Data Lakehouse."""
        try:
            # Generar ruta para el informe
            report_id = report["report_id"]
            today = datetime.now()
            year = today.year
            month = today.month
            day = today.day

            report_path = os.path.join(
                self.threat_report_path,
                str(year),
                f"{month:02d}",
                f"{day:02d}",
                f"threat_report_{report_id}.json"
            )

            # Crear directorios si no existen
            os.makedirs(os.path.dirname(report_path), exist_ok=True)

            # Guardar el informe
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)

            # Registrar la fuente de datos
            self._register_data_source(report_path, "threat_report", 1)

            return report_path

        except Exception as e:
            self.logger.error(f"Error al guardar informe de amenazas: {str(e)}")
            return ""

    def _process_network_data(self, network_data: Dict):
        """Procesa datos de red y los almacena en el Data Lakehouse."""
        try:
            # Extraer información de dispositivos
            if "changes" in network_data and "new_devices" in network_data["changes"]:
                for device in network_data["changes"]["new_devices"]:
                    device_data = {
                        "mac": device["mac"].upper(),
                        "ip": device["ip"],
                        "vendor": device["vendor"],
                        "timestamp": device["first_seen"],
                        "node_id": network_data.get("node_id"),
                        "source_type": "network_scan",
                        "source_path": network_data.get("source_path", ""),
                        "signal_strength": device.get("signal_strength", -100),
                        "location": network_data.get("location", ""),
                        "device_type": device.get("device_type", "unknown"),
                        "os": device.get("os", "unknown"),
                        "manufacturer": device.get("manufacturer", "unknown"),
                        "model": device.get("model", "unknown"),
                        "risk_score": 0.0,
                        "threat_level": "unknown"
                    }

                    # Almacenar en el Data Lakehouse
                    self._store_data("network", device_data, {
                        "source_id": f"network_{uuid.uuid4().hex[:16]}",
                        "source_type": "network_scan",
                        "node_id": network_data.get("node_id"),
                        "location": network_data.get("location", ""),
                        "file_path": network_data.get("source_path", "")
                    })

                    # Indexar el dispositivo
                    self._index_device_sighting(device_data)

                    # Buscar dispositivos similares
                    similar_devices = self._find_similar_devices(device_data["mac"])
                    if similar_devices:
                        self._create_device_relationships(device_data["mac"], similar_devices)

            # Procesar dispositivos desaparecidos
            if "changes" in network_data and "disappeared_devices" in network_data["changes"]:
                for device in network_data["changes"]["disappeared_devices"]:
                    device_data = {
                        "mac": device["mac"].upper(),
                        "ip": device["ip"],
                        "vendor": device["vendor"],
                        "timestamp": device["last_seen"],
                        "node_id": network_data.get("node_id"),
                        "source_type": "network_scan",
                        "source_path": network_data.get("source_path", ""),
                        "status": "disappeared"
                    }

                    # Registrar el evento de desaparición
                    self._store_data("network", device_data, {
                        "source_id": f"network_disappeared_{uuid.uuid4().hex[:16]}",
                        "source_type": "network_scan",
                        "node_id": network_data.get("node_id"),
                        "location": network_data.get("location", "")
                    })

        except Exception as e:
            self.logger.error(f"Error al procesar datos de red: {str(e)}")

    def _create_device_relationships(self, ref_mac: str, similar_devices: List[Dict]):
        """Crea relaciones entre dispositivos similares."""
        try:
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                # Obtener ID del dispositivo de referencia
                cursor.execute("""
                    SELECT id FROM devices WHERE mac = ?
                """, (ref_mac,))
                ref_device = cursor.fetchone()

                if not ref_device:
                    return

                ref_device_id = ref_device[0]

                for similar_device in similar_devices:
                    # Obtener ID del dispositivo similar
                    cursor.execute("""
                        SELECT id FROM devices WHERE mac = ?
                    """, (similar_device["mac"],))
                    similar_device_id = cursor.fetchone()

                    if not similar_device_id:
                        continue

                    similar_device_id = similar_device_id[0]

                    # Verificar si ya existe una relación
                    cursor.execute("""
                        SELECT id FROM device_relationships
                        WHERE (device1_id = ? AND device2_id = ?) OR (device1_id = ? AND device2_id = ?)
                    """, (ref_device_id, similar_device_id, similar_device_id, ref_device_id))

                    if cursor.fetchone():
                        continue  # Relación ya existe

                    # Crear nueva relación
                    relationship_type = "potential_duplicate"
                    strength = similar_device["similarity"] / 100.0  # Convertir a 0-1
                    confidence = min(1.0, strength * 0.9)  # Confianza ligeramente menor que la fuerza

                    cursor.execute("""
                        INSERT INTO device_relationships (
                            device1_id, device2_id, relationship_type, strength, confidence
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (ref_device_id, similar_device_id, relationship_type, strength, confidence))

                    conn.commit()

        except sqlite3.Error as e:
            self.logger.error(f"Error al crear relaciones de dispositivos: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error al crear relaciones de dispositivos: {str(e)}")

    def _process_osint_data(self, osint_data: Dict):
        """Procesa datos OSINT y los almacena en el Data Lakehouse."""
        try:
            # Almacenar datos OSINT
            self._store_data("osint", osint_data, {
                "source_id": f"osint_{uuid.uuid4().hex[:16]}",
                "source_type": "osint_scan",
                "node_id": osint_data.get("node_id"),
                "location": osint_data.get("location", "")
            })

            # Extraer información de dispositivos si está disponible
            if "domains" in osint_data:
                for domain in osint_data["domains"]:
                    domain_data = {
                        "type": "domain",
                        "name": domain,
                        "timestamp": osint_data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                        "source": osint_data.get("source", ""),
                        "related_data": osint_data
                    }
                    self._store_data("osint", domain_data, {
                        "source_id": f"osint_domain_{uuid.uuid4().hex[:16]}",
                        "source_type": "osint_domain",
                        "node_id": osint_data.get("node_id")
                    })

            if "subdomains" in osint_data:
                for subdomain in osint_data["subdomains"]:
                    subdomain_data = {
                        "type": "subdomain",
                        "name": subdomain,
                        "timestamp": osint_data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                        "source": osint_data.get("source", ""),
                        "related_data": osint_data
                    }
                    self._store_data("osint", subdomain_data, {
                        "source_id": f"osint_subdomain_{uuid.uuid4().hex[:16]}",
                        "source_type": "osint_subdomain",
                        "node_id": osint_data.get("node_id")
                    })

            if "vulnerabilities" in osint_data:
                for vulnerability in osint_data["vulnerabilities"]:
                    vuln_data = {
                        "type": "vulnerability",
                        "description": vulnerability.get("description", ""),
                        "severity": vulnerability.get("severity", "unknown"),
                        "type": vulnerability.get("type", ""),
                        "url": vulnerability.get("url", ""),
                        "confidence": vulnerability.get("confidence", 0.0),
                        "timestamp": osint_data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                        "source": osint_data.get("source", ""),
                        "related_data": osint_data
                    }
                    self._store_data("osint", vuln_data, {
                        "source_id": f"osint_vuln_{uuid.uuid4().hex[:16]}",
                        "source_type": "osint_vulnerability",
                        "node_id": osint_data.get("node_id")
                    })

        except Exception as e:
            self.logger.error(f"Error al procesar datos OSINT: {str(e)}")

    def _process_telemetry_data(self, telemetry_data: Dict):
        """Procesa datos de telemetría y los almacena en el Data Lakehouse."""
        try:
            # Almacenar datos de telemetría
            self._store_data("telemetry", telemetry_data, {
                "source_id": f"telemetry_{uuid.uuid4().hex[:16]}",
                "source_type": "node_telemetry",
                "node_id": telemetry_data.get("node_id"),
                "location": telemetry_data.get("location", "")
            })

            # Extraer información de dispositivos si está disponible
            if "devices" in telemetry_data:
                for device in telemetry_data["devices"]:
                    device_data = {
                        "mac": device.get("mac", "").upper(),
                        "ip": device.get("ip"),
                        "vendor": device.get("vendor", "Unknown"),
                        "timestamp": telemetry_data.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                        "node_id": telemetry_data.get("node_id"),
                        "source_type": "node_telemetry",
                        "source_path": telemetry_data.get("source_path", ""),
                        "signal_strength": device.get("signal_strength", -100),
                        "location": telemetry_data.get("location", ""),
                        "device_type": device.get("device_type", "unknown"),
                        "os": device.get("os", "unknown"),
                        "manufacturer": device.get("manufacturer", "unknown"),
                        "model": device.get("model", "unknown"),
                        "risk_score": device.get("risk_score", 0.0),
                        "threat_level": device.get("threat_level", "unknown")
                    }

                    # Indexar el dispositivo
                    self._index_device_sighting(device_data)

        except Exception as e:
            self.logger.error(f"Error al procesar datos de telemetría: {str(e)}")

    def _process_log_data(self, log_data: Dict):
        """Procesa datos de logs y los almacena en el Data Lakehouse."""
        try:
            # Almacenar datos de logs
            self._store_data("logs", log_data, {
                "source_id": f"log_{uuid.uuid4().hex[:16]}",
                "source_type": "system_log",
                "node_id": log_data.get("node_id"),
                "location": log_data.get("location", "")
            })

            # Extraer información de dispositivos si está disponible
            if "events" in log_data:
                for event in log_data["events"]:
                    if event.get("type") == "device_activity":
                        device_data = {
                            "mac": event.get("mac", "").upper(),
                            "ip": event.get("ip"),
                            "vendor": event.get("vendor", "Unknown"),
                            "timestamp": event.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                            "node_id": log_data.get("node_id"),
                            "source_type": "system_log",
                            "source_path": log_data.get("source_path", ""),
                            "event_type": event.get("type", "unknown"),
                            "event_details": event.get("details", ""),
                            "signal_strength": event.get("signal_strength", -100),
                            "location": log_data.get("location", ""),
                            "device_type": event.get("device_type", "unknown"),
                            "os": event.get("os", "unknown"),
                            "manufacturer": event.get("manufacturer", "unknown"),
                            "model": event.get("model", "unknown"),
                            "risk_score": event.get("risk_score", 0.0),
                            "threat_level": event.get("threat_level", "unknown")
                        }

                        # Indexar el dispositivo
                        self._index_device_sighting(device_data)

        except Exception as e:
            self.logger.error(f"Error al procesar datos de logs: {str(e)}")

    def _data_processor(self):
        """Procesa datos entrantes del sistema en segundo plano."""
        while not self.shutdown_event.is_set():
            try:
                self.logger.info("🔍 Procesando datos entrantes...")

                # En un entorno real, obtendríamos datos de múltiples fuentes
                # Por ahora, simulamos el procesamiento

                # Simular recepción de datos de red
                time.sleep(self.config.get("data_processing_interval", 60))

            except Exception as e:
                self.logger.error(f"Error en el procesador de datos: {str(e)}")
                time.sleep(self.config.get("error_retry_delay", 60))

    def _index_updater(self):
        """Actualiza el índice de dispositivos en segundo plano."""
        while not self.shutdown_event.is_set():
            try:
                self.logger.info("🔍 Actualizando índice de dispositivos...")

                # En un entorno real, actualizaríamos el índice con nuevos datos
                # Por ahora, solo mantenemos el índice activo

                # Verificar y limpiar datos antiguos
                self._cleanup_old_data()

                time.sleep(self.index_update_interval)

            except Exception as e:
                self.logger.error(f"Error en el actualizador de índice: {str(e)}")
                time.sleep(self.config.get("error_retry_delay", 60))

    def _threat_analyzer(self):
        """Analiza amenazas y genera informes semanales."""
        while not self.shutdown_event.is_set():
            try:
                self.logger.info("🔍 Analizando amenazas y generando informes...")

                # Calcular la fecha del informe (domingo de la semana pasada)
                today = datetime.now()
                start_date = today - timedelta(days=today.weekday() + 7)  # Domingo de la semana pasada
                end_date = start_date + timedelta(days=6)  # Sábado de la semana pasada

                # Generar informe de amenazas
                report = self._generate_threat_report(start_date, end_date)

                if report and "error" not in report:
                    # Guardar el informe
                    report_path = self._save_threat_report(report)
                    if report_path:
                        self.logger.info(f"✅ Informe de amenazas generado: {report_path}")

                # Esperar hasta la próxima ejecución (domingo a medianoche)
                next_run = today + timedelta(days=(6 - today.weekday()) % 7)  # Próximo domingo
                next_run = next_run.replace(hour=0, minute=0, second=0, microsecond=0)
                sleep_time = (next_run - today).total_seconds()

                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    time.sleep(24 * 3600)  # Esperar 24 horas si ya es domingo

            except Exception as e:
                self.logger.error(f"Error en el analizador de amenazas: {str(e)}")
                time.sleep(self.config.get("error_retry_delay", 60))

    def _cleanup_old_data(self):
        """Limpia datos antiguos según la política de retención."""
        try:
            retention_cutoff = datetime.now() - timedelta(days=self.retention_days)

            # Limpiar datos en la base de datos de índice
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                # Eliminar avistamientos antiguos
                cursor.execute("""
                    DELETE FROM device_sightings
                    WHERE timestamp < ?
                """, (retention_cutoff.isoformat() + "Z",))

                # Eliminar dispositivos sin avistamientos recientes
                cursor.execute("""
                    DELETE FROM devices
                    WHERE id NOT IN (
                        SELECT DISTINCT device_id
                        FROM device_sightings
                        WHERE timestamp >= ?
                    )
                """, (retention_cutoff.isoformat() + "Z",))

                # Eliminar relaciones antiguas
                cursor.execute("""
                    DELETE FROM device_relationships
                    WHERE timestamp < ?
                """, (retention_cutoff.isoformat() + "Z",))

                # Eliminar fuentes de datos antiguas
                cursor.execute("""
                    DELETE FROM data_sources
                    WHERE timestamp < ?
                """, (retention_cutoff.isoformat() + "Z",))

                conn.commit()
                conn.close()

                self.logger.info(f"🧹 Datos antiguos limpiados (antes de {retention_cutoff.date()})")

            # Limpiar archivos en el Data Lakehouse
            for data_type in ["telemetry", "osint", "network", "logs"]:
                base_path = getattr(self, f"{data_type}_path")
                self._cleanup_old_files(base_path, retention_cutoff)

        except Exception as e:
            self.logger.error(f"Error al limpiar datos antiguos: {str(e)}")

    def _cleanup_old_files(self, base_path: str, cutoff_date: datetime):
        """Limpia archivos antiguos en un directorio específico."""
        try:
            for year in range(2020, datetime.now().year + 1):
                year_path = os.path.join(base_path, str(year))
                if not os.path.exists(year_path):
                    continue

                for month in range(1, 13):
                    month_path = os.path.join(year_path, f"{month:02d}")
                    if not os.path.exists(month_path):
                        continue

                    for day in range(1, 32):
                        day_path = os.path.join(month_path, f"{day:02d}")
                        if not os.path.exists(day_path):
                            continue

                        # Verificar si el día está antes de la fecha de corte
                        day_date = datetime(year, month, day)
                        if day_date < cutoff_date:
                            # Eliminar todos los archivos en este día
                            for file_type in ["json", "parquet", "zstd", "lzma"]:
                                type_path = os.path.join(day_path, file_type)
                                if os.path.exists(type_path):
                                    for file_name in os.listdir(type_path):
                                        file_path = os.path.join(type_path, file_name)
                                        try:
                                            os.remove(file_path)
                                        except:
                                            pass

                            # Eliminar directorio vacío
                            try:
                                os.rmdir(day_path)
                            except:
                                pass

                            self.logger.info(f"🧹 Directorio eliminado: {day_path}")

        except Exception as e:
            self.logger.error(f"Error al limpiar archivos antiguos en {base_path}: {str(e)}")

    def process_network_scan(self, network_data: Dict):
        """Procesa un escaneo de red recibido."""
        try:
            self._process_network_data(network_data)
            return True
        except Exception as e:
            self.logger.error(f"Error al procesar escaneo de red: {str(e)}")
            return False

    def process_osint_scan(self, osint_data: Dict):
        """Procesa un escaneo OSINT recibido."""
        try:
            self._process_osint_data(osint_data)
            return True
        except Exception as e:
            self.logger.error(f"Error al procesar escaneo OSINT: {str(e)}")
            return False

    def process_telemetry_data(self, telemetry_data: Dict):
        """Procesa datos de telemetría recibidos."""
        try:
            self._process_telemetry_data(telemetry_data)
            return True
        except Exception as e:
            self.logger.error(f"Error al procesar datos de telemetría: {str(e)}")
            return False

    def process_log_data(self, log_data: Dict):
        """Procesa datos de logs recibidos."""
        try:
            self._process_log_data(log_data)
            return True
        except Exception as e:
            self.logger.error(f"Error al procesar datos de logs: {str(e)}")
            return False

    def find_device(self, mac: str, fuzzy_match: bool = True) -> Optional[Dict]:
        """Busca un dispositivo por MAC (con opción de fuzzy matching)."""
        try:
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                # Buscar dispositivo exacto
                cursor.execute("""
                    SELECT id, mac, ip, vendor, first_seen, last_seen, related_events, risk_score, threat_level
                    FROM devices
                    WHERE mac = ?
                """, (mac.upper(),))

                device = cursor.fetchone()

                if device:
                    # Obtener avistamientos recientes
                    cursor.execute("""
                        SELECT timestamp, node_id, location, signal_strength, ip_address, vendor,
                               device_type, os, manufacturer, model, risk_score, threat_level, source_type
                        FROM device_sightings
                        WHERE device_id = ?
                        ORDER BY timestamp DESC
                        LIMIT 10
                    """, (device[0],))

                    sightings = cursor.fetchall()

                    result = {
                        "device": {
                            "id": device[0],
                            "mac": device[1],
                            "ip": device[2],
                            "vendor": device[3],
                            "first_seen": device[4],
                            "last_seen": device[5],
                            "related_events": device[6],
                            "risk_score": device[7],
                            "threat_level": device[8],
                            "behavior_analysis": self._analyze_device_behavior(device[0])
                        },
                        "recent_sightings": [
                            {
                                "timestamp": sighting[0],
                                "node_id": sighting[1],
                                "location": sighting[2],
                                "signal_strength": sighting[3],
                                "ip_address": sighting[4],
                                "vendor": sighting[5],
                                "device_type": sighting[6],
                                "os": sighting[7],
                                "manufacturer": sighting[8],
                                "model": sighting[9],
                                "risk_score": sighting[10],
                                "threat_level": sighting[11],
                                "source_type": sighting[12]
                            }
                            for sighting in sightings
                        ],
                        "related_devices": self._find_related_devices(device[0])
                    }

                    return result
                elif fuzzy_match:
                    # Buscar dispositivos similares usando fuzzy matching
                    similar_devices = self._find_similar_devices(mac.upper())
                    if similar_devices:
                        return {
                            "message": "Dispositivo no encontrado exactamente, pero se encontraron dispositivos similares",
                            "similar_devices": similar_devices,
                            "analysis": self._analyze_potential_match(mac.upper(), similar_devices)
                        }

                return None

        except sqlite3.Error as e:
            self.logger.error(f"Error al buscar dispositivo: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error al buscar dispositivo: {str(e)}")
            return None

    def _analyze_potential_match(self, query_mac: str, similar_devices: List[Dict]) -> Dict:
        """Analiza la posibilidad de que un dispositivo sea un match aproximado."""
        analysis = {
            "query_mac": query_mac,
            "similar_devices": [],
            "best_match": None,
            "confidence": 0.0,
            "recommendations": []
        }

        # Encontrar el mejor match
        best_match = max(similar_devices, key=lambda x: x["similarity"], default=None)
        if best_match:
            analysis["best_match"] = {
                "device_id": best_match["id"],
                "mac": best_match["mac"],
                "ip": best_match["ip"],
                "vendor": best_match["vendor"],
                "similarity": best_match["similarity"],
                "common_features": self._find_common_features_with_query(query_mac, best_match["mac"])
            }
            analysis["confidence"] = best_match["similarity"] / 100.0

        # Analizar dispositivos similares
        for device in similar_devices:
            analysis["similar_devices"].append({
                "device_id": device["id"],
                "mac": device["mac"],
                "ip": device["ip"],
                "vendor": device["vendor"],
                "similarity": device["similarity"],
                "risk_score": device.get("risk_score", 0.0),
                "threat_level": device.get("threat_level", "unknown")
            })

        # Generar recomendaciones
        if best_match and analysis["confidence"] > 0.7:
            analysis["recommendations"].append({
                "action": "investigate",
                "description": "El dispositivo parece ser un match aproximado con alta confianza. "
                               "Investigar para confirmar si es el mismo dispositivo con MAC diferente.",
                "severity": "medium"
            })

            if best_match["threat_level"] in ["high", "critical"]:
                analysis["recommendations"].append({
                    "action": "quarantine",
                    "description": "El dispositivo similar tiene un nivel de amenaza alto. "
                               "Considerar cuarentena preventiva.",
                    "severity": "high"
                })

        elif similar_devices:
            analysis["recommendations"].append({
                "action": "manual_review",
                "description": "Se encontraron dispositivos similares, pero con baja confianza. "
                               "Revisar manualmente los logs y datos para determinar si están relacionados.",
                "severity": "low"
            })

        return analysis

    def _find_common_features_with_query(self, query_mac: str, device_mac: str) -> Dict:
        """Encuentra características comunes entre un MAC de consulta y un dispositivo."""
        try:
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                # Obtener avistamientos del dispositivo
                cursor.execute("""
                    SELECT ip_address, vendor, device_type, os, manufacturer, model, timestamp
                    FROM device_sightings
                    WHERE device_id = ?
                    ORDER BY timestamp DESC
                    LIMIT 10
                """, (device_mac,))  # Asumiendo que device_mac es el ID del dispositivo

                sightings = cursor.fetchall()

                if not sightings:
                    return {"message": "No se encontraron avistamientos para el dispositivo"}

                # Crear un perfil simplificado basado en los avistamientos
                profile = {
                    "ip_patterns": set(),
                    "vendors": set(),
                    "device_types": set(),
                    "oses": set(),
                    "manufacturers": set(),
                    "models": set(),
                    "timestamps": []
                }

                for sighting in sightings:
                    # Extraer patrones de IP
                    ip = sighting[0]
                    if ip:
                        ip_parts = ip.split('.')
                        if len(ip_parts) == 4:
                            ip_pattern = f"{ip_parts[0]}.{ip_parts[1]}"
                            profile["ip_patterns"].add(ip_pattern)

                    # Extraer vendor
                    vendor = sighting[1]
                    if vendor:
                        profile["vendors"].add(vendor.lower())

                    # Extraer device_type
                    device_type = sighting[2]
                    if device_type:
                        profile["device_types"].add(device_type.lower())

                    # Extraer OS
                    os_info = sighting[3]
                    if os_info:
                        profile["oses"].add(os_info.lower())

                    # Extraer manufacturer
                    manufacturer = sighting[4]
                    if manufacturer:
                        profile["manufacturers"].add(manufacturer.lower())

                    # Extraer model
                    model = sighting[5]
                    if model:
                        profile["models"].add(model.lower())

                    # Extraer timestamps
                    timestamp = sighting[6]
                    try:
                        dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
                        profile["timestamps"].append(dt)
                    except:
                        pass

                # Comparar con el MAC de consulta (primeros 3 bytes suelen ser del fabricante)
                mac_pattern = query_mac[:8]  # Primeros 8 caracteres (primeros 3 bytes MAC)
                common_features = {
                    "mac_pattern_match": mac_pattern in profile["manufacturers"],
                    "ip_patterns": list(profile["ip_patterns"]),
                    "vendors": list(profile["vendors"]),
                    "device_types": list(profile["device_types"]),
                    "oses": list(profile["oses"]),
                    "manufacturers": list(profile["manufacturers"]),
                    "models": list(profile["models"]),
                    "time_patterns": self._analyze_time_patterns(profile["timestamps"])
                }

                return common_features

        except sqlite3.Error as e:
            self.logger.error(f"Error al encontrar características comunes: {str(e)}")
            return {"error": str(e)}
        except Exception as e:
            self.logger.error(f"Error al encontrar características comunes: {str(e)}")
            return {"error": str(e)}

    def _analyze_time_patterns(self, timestamps: List[datetime]) -> Dict:
        """Analiza patrones temporales de avistamientos."""
        if not timestamps:
            return {"message": "No hay datos temporales disponibles"}

        # Calcular estadísticas temporales
        time_diffs = [(timestamps[i+1] - timestamps[i]).total_seconds() for i in range(len(timestamps)-1)]

        avg_time_between = np.mean(time_diffs) if time_diffs else 0
        std_time_between = np.std(time_diffs) if time_diffs else 0

        # Analizar distribución por hora del día
        hours = [t.hour for t in timestamps]
        hour_counts = np.bincount(hours, minlength=24)

        # Analizar distribución por día de la semana
        days = [t.weekday() for t in timestamps]
        day_counts = np.bincount(days, minlength=7)

        return {
            "average_time_between_sightings_seconds": avg_time_between,
            "standard_deviation_seconds": std_time_between,
            "hourly_distribution": {i: count for i, count in enumerate(hour_counts) if count > 0},
            "daily_distribution": {i: count for i, count in enumerate(day_counts) if count > 0},
            "time_range_days": (timestamps[-1] - timestamps[0]).days if len(timestamps) > 1 else 0,
            "most_active_hours": sorted(
                [(hour, count) for hour, count in enumerate(hour_counts) if count > 0],
                key=lambda x: x[1], reverse=True
            )[:3],
            "most_active_days": sorted(
                [(day, count) for day, count in enumerate(day_counts) if count > 0],
                key=lambda x: x[1], reverse=True
            )[:3]
        }

    def get_threat_intel(self, threat_type: str = None, severity: str = None) -> List[Dict]:
        """Obtiene inteligencia de amenazas de la base de datos."""
        try:
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                query = """
                    SELECT id, threat_id, threat_type, description, severity, confidence,
                           first_seen, last_seen, related_devices, related_events, indicators, references
                    FROM threat_intel
                """
                params = []

                conditions = []
                if threat_type:
                    conditions.append("threat_type = ?")
                    params.append(threat_type)
                if severity:
                    conditions.append("severity = ?")
                    params.append(severity)

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                query += " ORDER BY severity DESC, confidence DESC, first_seen DESC"

                cursor.execute(query, params)
                threats = cursor.fetchall()

                return [{
                    "id": threat[0],
                    "threat_id": threat[1],
                    "threat_type": threat[2],
                    "description": threat[3],
                    "severity": threat[4],
                    "confidence": threat[5],
                    "first_seen": threat[6],
                    "last_seen": threat[7],
                    "related_devices": threat[8],
                    "related_events": threat[9],
                    "indicators": threat[10],
                    "references": threat[11],
                    "devices": self._get_threat_related_devices(threat[1])
                } for threat in threats]

        except sqlite3.Error as e:
            self.logger.error(f"Error al obtener inteligencia de amenazas: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error al obtener inteligencia de amenazas: {str(e)}")
            return []

    def get_device_relationships(self, device_id: int, min_strength: float = 0.5) -> List[Dict]:
        """Obtiene relaciones entre dispositivos."""
        try:
            with self.index_lock:
                conn = sqlite3.connect(self.index_path)
                cursor = conn.cursor()

                # Obtener relaciones del dispositivo
                cursor.execute("""
                    SELECT device1_id, device2_id, relationship_type, strength, confidence, evidence, timestamp
                    FROM device_relationships
                    WHERE (device1_id = ? OR device2_id = ?) AND strength >= ?
                    ORDER BY strength DESC, confidence DESC
                """, (device_id, device_id, min_strength))

                relationships = cursor.fetchall()

                result = []
                for rel in relationships:
                    if rel[0] == device_id:
                        other_device_id = rel[1]
                    else:
                        other_device_id = rel[0]

                    # Obtener información del otro dispositivo
                    cursor.execute("""
                        SELECT id, mac, ip, vendor, risk_score, threat_level
                        FROM devices
                        WHERE id = ?
                    """, (other_device_id,))
                    other_device = cursor.fetchone()

                    if other_device:
                        result.append({
                            "device1_id": rel[0],
                            "device1_mac": device_id if rel[0] == device_id else other_device[1],
                            "device2_id": rel[1],
                            "device2_mac": other_device[1] if rel[0] == device_id else device_id,
                            "relationship_type": rel[2],
                            "strength": rel[3],
                            "confidence": rel[4],
                            "evidence": rel[5],
                            "timestamp": rel[6],
                            "other_device": {
                                "id": other_device[0],
                                "mac": other_device[1],
                                "ip": other_device[2],
                                "vendor": other_device[3],
                                "risk_score": other_device[4],
                                "threat_level": other_device[5]
                            }
                        })

                return result

        except sqlite3.Error as e:
            self.logger.error(f"Error al obtener relaciones de dispositivos: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error al obtener relaciones de dispositivos: {str(e)}")
            return []

    def start(self):
        """Inicia el Data Lakehouse."""
        self.running = True
        self.shutdown_event.clear()
        self.logger.info("🚀 Data Lakehouse iniciado")

        # Iniciar hilos de procesamiento
        self.data_processor_thread = threading.Thread(
            target=self._data_processor,
            daemon=True,
            name="DataProcessorThread"
        )
        self.data_processor_thread.start()

        self.index_updater_thread = threading.Thread(
            target=self._index_updater,
            daemon=True,
            name="IndexUpdaterThread"
        )
        self.index_updater_thread.start()

        self.threat_analyzer_thread = threading.Thread(
            target=self._threat_analyzer,
            daemon=True,
            name="ThreatAnalyzerThread"
        )
        self.threat_analyzer_thread.start()

        # Esperar a que se presione Ctrl+C
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("🛑 Data Lakehouse detenido por el usuario")
        finally:
            self.stop()

    def stop(self):
        """Detiene el Data Lakehouse."""
        if self.running:
            self.running = False
            self.shutdown_event.set()

            # Esperar a que los hilos terminen
            if self.data_processor_thread:
                self.data_processor_thread.join(timeout=5)
            if self.index_updater_thread:
                self.index_updater_thread.join(timeout=5)
            if self.threat_analyzer_thread:
                self.threat_analyzer_thread.join(timeout=5)

            self.logger.info("🛑 Data Lakehouse detenido")

def load_config(config_file: str = "/data/data/com.termux/files/home/data_lakehouse_config.json") -> Dict:
    """Carga la configuración desde un archivo JSON."""
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        return config
    except Exception as e:
        raise ValueError(f"Error al cargar configuración: {str(e)}")

def save_config(config: Dict, config_file: str = "/data/data/com.termux/files/home/data_lakehouse_config.json"):
    """Guarda la configuración en un archivo JSON."""
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        raise ValueError(f"Error al guardar configuración: {str(e)}")

def setup_default_config() -> Dict:
    """Configura valores por defecto para el Data Lakehouse."""
    return {
        "version": "1.0.0",
        "description": "Configuración para el Data Lakehouse de AURA",
        "node_id": "server_node_001",
        "db_path": "/data/data/com.termux/files/home/aura_intel.db",
        "data_lake_root": "/data/data/com.termux/files/home/aura_data_lake",
        "index_path": "/data/data/com.termux/files/home/aura_index.db",
        "telemetry_path": "/data/data/com.termux/files/home/aura_telemetry",
        "osint_path": "/data/data/com.termux/files/home/aura_osint",
        "network_path": "/data/data/com.termux/files/home/aura_network",
        "log_path": "/data/data/com.termux/files/home/aura_logs",
        "threat_report_path": "/data/data/com.termux/files/home/threat_reports",
        "max_file_size_mb": 100,
        "max_files_per_dir": 1000,
        "index_update_interval": 3600,
        "retention_days": 90,
        "compression_level": 6,
        "data_processing_interval": 60,
        "error_retry_delay": 60,
        "log_file": "/data/data/com.termux/files/home/data_lakehouse.log",
        "enable_compression": true,
        "compression_method": "zstd",
        "enable_indexing": true,
        "indexing_threads": 4,
        "fuzzy_matching_threshold": 80,
        "device_relationship_threshold": 0.7,
        "threat_analysis_interval": 604800,  # 1 semana en segundos
        "security_settings": {
            "enable_data_encryption": true,
            "encryption_key_path": "/data/data/com.termux/files/home/data_encryption.key",
            "enable_access_control": true,
            "allowed_ips": ["127.0.0.1", "192.168.1.0/24"],
            "api_rate_limit": 100,
            "rate_limit_window": 60
        },
        "performance_settings": {
            "cache_enabled": true,
            "cache_size_mb": 512,
            "parallel_processing": true,
            "max_parallel_tasks": 8,
            "query_timeout": 30,
            "indexing_timeout": 60
        },
        "data_sources": {
            "network_scans": {
                "enabled": true,
                "path": "/data/data/com.termux/files/home/aura_network",
                "file_format": "json",
                "processing_interval": 60
            },
            "osint_scans": {
                "enabled": true,
                "path": "/data/data/com.termux/files/home/aura_osint",
                "file_format": "json",
                "processing_interval": 300
            },
            "telemetry_data": {
                "enabled": true,
                "path": "/data/data/com.termux/files/home/aura_telemetry",
                "file_format": "parquet",
                "processing_interval": 300
            },
            "system_logs": {
                "enabled": true,
                "path": "/data/data/com.termux/files/home/aura_logs",
                "file_format": "json",
                "processing_interval": 60
            }
        },
        "threat_intel_settings": {
            "enabled": true,
            "threat_levels": {
                "critical": {"score": 90, "color": "#F44336"},
                "high": {"score": 70, "color": "#FF9800"},
                "medium": {"score": 50, "color": "#FFC107"},
                "low": {"score": 30, "color": "#4CAF50"},
                "unknown": {"score": 0, "color": "#9E9E9E"}
            },
            "risk_assessment": {
                "ip_changes_weight": 0.2,
                "mac_changes_weight": 0.2,
                "vendor_changes_weight": 0.1,
                "behavior_score_weight": 0.3,
                "threat_history_weight": 0.2
            },
            "reporting": {
                "enabled": true,
                "schedule": "weekly",
                "recipients": ["security@aura-system.com"],
                "format": "json",
                "retention_days": 365
            }
        },
        "correlation_settings": {
            "enabled": true,
            "fuzzy_matching": {
                "enabled": true,
                "threshold": 80,
                "mac_pattern_length": 8,
                "ip_pattern_length": 2
            },
            "device_relationships": {
                "enabled": true,
                "min_similarity": 0.7,
                "max_relationships": 50
            },
            "time_window_days": 30,
            "location_threshold_km": 10
        },
        "last_updated": "2026-06-02T00:00:00Z"
    }

def main():
    """Punto de entrada principal del Data Lakehouse."""
    parser = argparse.ArgumentParser(description="Data Lakehouse para almacenamiento e indexación de datos históricos de AURA.")
    parser.add_argument("--config", help="Archivo de configuración JSON", default="/data/data/com.termux/files/home/data_lakehouse_config.json")
    parser.add_argument("--setup", action="store_true", help="Configurar valores por defecto")
    parser.add_argument("--test", action="store_true", help="Realizar pruebas de configuración")
    parser.add_argument("--find", help="Buscar un dispositivo por MAC")
    parser.add_argument("--report", action="store_true", help="Generar informe de amenazas semanal")
    args = parser.parse_args()

    try:
        if args.setup:
            config = setup_default_config()
            save_config(config)
            print("✅ Configuración por defecto guardada en data_lakehouse_config.json")
            print("Por favor edita este archivo según tu configuración antes de iniciar el servicio.")
            return

        config = load_config(args.config)
        lakehouse = DataLakehouse(config)

        if args.test:
            print("🔍 Realizando pruebas de configuración...")
            print(f"📡 Data Lakehouse configurado con:")
            print(f"   - Base de datos: {config['db_path']}")
            print(f"   - Data Lake Root: {config['data_lake_root']}")
            print(f"   - Retención de datos: {config['retention_days']} días")
            print(f"   - Compresión: {'Habilitada' if config['enable_compression'] else 'Deshabilitada'}")
            print(f"   - Indexación: {'Habilitada' if config['enable_indexing'] else 'Deshabilitada'}")
            return

        if args.find:
            device_info = lakehouse.find_device(args.find)
            if device_info:
                print(f"🔍 Información del dispositivo {args.find}:")
                if "device" in device_info:
                    device = device_info["device"]
                    print(f"   MAC: {device['mac']}")
                    print(f"   IP: {device['ip']}")
                    print(f"   Vendor: {device['vendor']}")
                    print(f"   Primer avistamiento: {device['first_seen']}")
                    print(f"   Último avistamiento: {device['last_seen']}")
                    print(f"   Avistamientos relacionados: {device['related_events']}")
                    print(f"   Puntuación de riesgo: {device['risk_score']}")
                    print(f"   Nivel de amenaza: {device['threat_level']}")

                    if "recent_sightings" in device_info:
                        print(f"   Últimos avistamientos ({len(device_info['recent_sightings'])}):")
                        for sighting in device_info["recent_sightings"][:3]:
                            print(f"     - {sighting['timestamp']}: {sighting['ip_address']} (Señal: {sighting['signal_strength']}dBm)")
                elif "similar_devices" in device_info:
                    print(f"🔍 No se encontró dispositivo exacto, pero se encontraron {len(device_info['similar_devices'])} dispositivos similares:")
                    for device in device_info["similar_devices"][:5]:
                        print(f"     - {device['mac']} (Similitud: {device['similarity']}%) - {device['vendor']}")
            else:
                print(f"❌ No se encontró información para el dispositivo {args.find}")
            return

        if args.report:
            # Generar informe para la semana pasada
            today = datetime.now()
            start_date = today - timedelta(days=today.weekday() + 7)  # Domingo de la semana pasada
            end_date = start_date + timedelta(days=6)  # Sábado de la semana pasada

            report = lakehouse._generate_threat_report(start_date, end_date)
            if report and "error" not in report:
                report_path = lakehouse._save_threat_report(report)
                if report_path:
                    print(f"✅ Informe de amenazas generado: {report_path}")
                    print(f"   Período: {report['period']['start_date']} a {report['period']['end_date']}")
                    print(f"   Dispositivos analizados: {report['summary'].get('total_devices', 0)}")
                    print(f"   Amenazas detectadas: {report['summary'].get('new_threats', 0)}")
                    print(f"   Dispositivos de alto riesgo: {len([d for d in report['devices'] if d['threat_level'] in ['high', 'critical']])}")
            else:
                print("❌ Error al generar informe de amenazas")
            return

        print("🚀 Data Lakehouse listo para uso.")
        print("Ejemplos de uso:")
        print("  python data_lakehouse.py --setup (Configurar valores por defecto)")
        print("  python data_lakehouse.py --test (Realizar pruebas de configuración)")
        print("  python data_lakehouse.py --find AA:BB:CC:DD:EE:FF (Buscar dispositivo)")
        print("  python data_lakehouse.py --report (Generar informe de amenazas semanal)")
        print("  python data_lakehouse.py (Iniciar Data Lakehouse en segundo plano)")

        # Iniciar el Data Lakehouse
        lakehouse.start()

    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()