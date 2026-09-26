"""
Módulo de gestión de la base de datos SQLite para AURA.
Centraliza la inteligencia recolectada en tablas estructuradas.
"""

import os
import sqlite3
from datetime import datetime
import re

# Ruta de la base de datos
DB_PATH = os.path.join(os.path.dirname(__file__), "Database", "aura_intelligence.db")

# Base de datos de asignación de fabricantes (OUI Lookup)
# Formato: {primeros_3_octetos: "Fabricante"}
OUI_DATABASE = {
    "00:0C:29": "VMware, Inc.",
    "00:13:37": "Apple, Inc.",
    "00:14:22": "Apple, Inc.",
    "00:16:CB": "Apple, Inc.",
    "00:18:84": "Apple, Inc.",
    "00:1A:4B": "Apple, Inc.",
    "00:1B:63": "Apple, Inc.",
    "00:50:F2": "Microsoft Corporation",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:16:3E": "Huawei Technologies Co., Ltd",
    "00:18:8B": "Huawei Technologies Co., Ltd",
    "00:1D:D1": "Samsung Electronics Co., Ltd",
    "00:1E:4F": "Samsung Electronics Co., Ltd",
    "00:23:12": "Samsung Electronics Co., Ltd",
    "00:0F:E2": "TP-Link Technologies Co., Ltd.",
    "00:11:2F": "TP-Link Technologies Co., Ltd.",
    "00:13:EF": "TP-Link Technologies Co., Ltd.",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:1D:4F": "D-Link Corporation",
    "00:26:B0": "D-Link Corporation",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgear, Inc.",
    "00:1D:0F": "Netgear, Inc.",
    "00:21:5A": "Netgear, Inc.",
    "00:0D:4B": "Huawei Technologies Co., Ltd",
    "00:18:F3": "Xiaomi Inc.",
    "00:1E:C2": "Xiaomi Inc.",
    "00:1F:33": "Xiaomi Inc.",
    "00:0C:42": "Intel Corporate",
    "00:1A:79": "Intel Corporate",
    "00:1C:1B": "Google, Inc.",
    "00:1E:8C": "Google, Inc.",
    "00:1F:5B": "Google, Inc.",
    "00:25:4B": "Amazon Technologies Inc.",
    "00:17:88": "Amazon Technologies Inc.",
    "00:0F:1F": "Netgeedar, Inc."
}

def ensure_database_directory():
    """Asegura que el directorio de la base de datos exista."""
    db_dir = os.path.dirname(DB_PATH)
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

def init_database():
    """Inicializa la base de datos y crea las tablas necesarias."""
    ensure_database_directory()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Crear tabla para búsquedas OSINT
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tabla_osint (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            platform TEXT NOT NULL,
            result_title TEXT,
            snippet TEXT,
            url TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Crear tabla para escaneos de radar
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tabla_radar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ssid TEXT NOT NULL,
            bssid TEXT NOT NULL,
            signal_strength INTEGER NOT NULL,
            manufacturer TEXT,
            device_type TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Crear tabla para alertas del centinela
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tabla_centinela (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            trigger_level REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Crear tabla para análisis de presencia
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tabla_presencia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER,
            network_id INTEGER,
            rssi_initial INTEGER,
            rssi_current INTEGER,
            perturbation_index REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (network_id) REFERENCES tabla_radar(id)
        )
        """)

        # Crear índice para mejorar el rendimiento en consultas por timestamp
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_osint_timestamp ON tabla_osint(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_radar_timestamp ON tabla_radar(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_centinela_timestamp ON tabla_centinela(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_presencia_timestamp ON tabla_presencia(timestamp)")

        conn.commit()

def lookup_manufacturer(bssid):
    """Realiza una búsqueda de OUI para identificar el fabricante del dispositivo."""
    if not bssid or len(bssid.split(':')) != 6:
        return None

    # Extraer los primeros 3 octetos (formato MAC)
    first_three = ':'.join(bssid.split(':')[:3]).upper()

    # Buscar en la base de datos de OUI
    return OUI_DATABASE.get(first_three, "Fabricante desconocido")

def determine_device_type(bssid, ssid):
    """Determina el tipo de dispositivo basado en la MAC y el SSID."""
    manufacturer = lookup_manufacturer(bssid)

    if not manufacturer:
        return "Tipo desconocido"

    # Lógica para determinar el tipo de dispositivo
    ssid_lower = ssid.lower()

    if "apple" in manufacturer.lower() or "google" in manufacturer.lower():
        if "iphone" in ssid_lower or "ipad" in ssid_lower or "apple" in ssid_lower:
            return "Dispositivo iOS"
        elif "android" in ssid_lower or "google" in ssid_lower:
            return "Dispositivo Android"
        else:
            return "Dispositivo móvil"

    elif "huawei" in manufacturer.lower() or "xiaomi" in manufacturer.lower():
        if "huawei" in ssid_lower or "honor" in ssid_lower:
            return "Smartphone Huawei"
        elif "mi" in ssid_lower or "xiaomi" in ssid_lower:
            return "Smartphone Xiaomi"
        else:
            return "Dispositivo inteligente"

    elif "samsung" in manufacturer.lower():
        if "galaxy" in ssid_lower or "samsung" in ssid_lower:
            return "Smartphone Samsung"
        elif "smart" in ssid_lower or "tv" in ssid_lower:
            return "Smart TV Samsung"
        else:
            return "Dispositivo Samsung"

    elif "vmware" in manufacturer.lower():
        return "Máquina virtual"

    elif "intel" in manufacturer.lower():
        return "Dispositivo con chip Intel"

    elif "netgear" in manufacturer.lower() or "tp-link" in manufacturer.lower() or "d-link" in manufacturer.lower():
        return "Router/Point de acceso"

    elif "amazon" in manufacturer.lower():
        return "Dispositivo Amazon (Echo, etc.)"

    else:
        return "Dispositivo genérico"

def save_radar_scan(ssid, bssid, signal_strength):
    """Guarda un escaneo de radar en la base de datos con información de fabricante y tipo de dispositivo."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Determinar fabricante y tipo de dispositivo
        manufacturer = lookup_manufacturer(bssid)
        device_type = determine_device_type(bssid, ssid)

        cursor.execute("""
        INSERT INTO tabla_radar (ssid, bssid, signal_strength, manufacturer, device_type)
        VALUES (?, ?, ?, ?, ?)
        """, (ssid, bssid, signal_strength, manufacturer, device_type))

        conn.commit()
    return cursor.lastrowid

def analyze_presence_changes(previous_scans, current_scans, threshold=15):
    """
    Analiza cambios en la fuerza de señal entre escaneos consecutivos.
    Calcula un índice de perturbación del entorno.
    """
    perturbation_results = []

    # Obtener los IDs de las redes en el escaneo actual
    current_networks = {scan['bssid']: scan for scan in current_scans}

    for prev_scan in previous_scans:
        bssid = prev_scan['bssid']
        if bssid in current_networks:
            current_scan = current_networks[bssid]
            rssi_initial = prev_scan['signal_strength']
            rssi_current = current_scan['signal_strength']

            # Calcular la diferencia de RSSI
            rssi_diff = abs(rssi_initial - rssi_current)

            # Calcular índice de perturbación (0-100)
            perturbation_index = min(100, (rssi_diff / threshold) * 100)

            if perturbation_index > 20:  # Umbral para considerar significativo
                perturbation_results.append({
                    'network_id': prev_scan.get('id'),
                    'rssi_initial': rssi_initial,
                    'rssi_current': rssi_current,
                    'perturbation_index': perturbation_index,
                    'ssid': prev_scan['ssid'],
                    'bssid': bssid
                })

    return perturbation_results

def save_presence_analysis(perturbation_results, scan_id):
    """Guarda el análisis de perturbación en la base de datos."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        for result in perturbation_results:
            cursor.execute("""
            INSERT INTO tabla_presencia (scan_id, network_id, rssi_initial, rssi_current, perturbation_index)
            VALUES (?, ?, ?, ?, ?)
            """, (
                scan_id,
                result['network_id'],
                result['rssi_initial'],
                result['rssi_current'],
                result['perturbation_index']
            ))

        conn.commit()
    return len(perturbation_results)

def get_radar_history_with_details(limit=100):
    """Obtiene el historial de escaneos de radar con detalles de fabricante y tipo de dispositivo."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM tabla_radar
        ORDER BY timestamp DESC
        LIMIT ?
        """, (limit,))
        return cursor.fetchall()

def get_presence_analysis(limit=50):
    """Obtiene el análisis de perturbación más reciente."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
        SELECT p.*, r.ssid, r.bssid, r.manufacturer, r.device_type
        FROM tabla_presencia p
        JOIN tabla_radar r ON p.network_id = r.id
        ORDER BY p.timestamp DESC
        LIMIT ?
        """, (limit,))
        return cursor.fetchall()

def save_osint_result(query, platform, result_title, snippet, url):
    """Guarda un resultado de búsqueda OSINT en la base de datos."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO tabla_osint (query, platform, result_title, snippet, url)
        VALUES (?, ?, ?, ?, ?)
        """, (query, platform, result_title, snippet, url))
        conn.commit()
    return cursor.lastrowid

def save_sentinel_alert(file_path, trigger_level):
    """Guarda una alerta del centinela en la base de datos."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO tabla_centinela (file_path, trigger_level)
        VALUES (?, ?)
        """, (file_path, trigger_level))
        conn.commit()
    return cursor.lastrowid

def get_osint_history(limit=100):
    """Obtiene el historial de búsquedas OSINT."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM tabla_osint
        ORDER BY timestamp DESC
        LIMIT ?
        """, (limit,))
        return cursor.fetchall()

def get_sentinel_history(limit=100):
    """Obtiene el historial de alertas del centinela."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
        SELECT * FROM tabla_centinela
        ORDER BY timestamp DESC
        LIMIT ?
        """, (limit,))
        return cursor.fetchall()

def get_recent_activity(limit=50):
    """Obtiene las últimas actividades de todos los módulos."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Consultar OSINT
        cursor.execute("""
        SELECT 'osint' as type, * FROM tabla_osint
        ORDER BY timestamp DESC
        LIMIT ?
        """, (limit//3,))

        osint_results = []
        for row in cursor.fetchall():
            row = dict(row)
            row['type'] = 'osint'
            osint_results.append(row)

        # Consultar Radar
        cursor.execute("""
        SELECT 'radar' as type, * FROM tabla_radar
        ORDER BY timestamp DESC
        LIMIT ?
        """, (limit//3,))

        radar_results = []
        for row in cursor.fetchall():
            row = dict(row)
            row['type'] = 'radar'
            radar_results.append(row)

        # Consultar Centinela
        cursor.execute("""
        SELECT 'centinela' as type, * FROM tabla_centinela
        ORDER BY timestamp DESC
        LIMIT ?
        """, (limit//3,))

        centinela_results = []
        for row in cursor.fetchall():
            row = dict(row)
            row['type'] = 'centinela'
            centinela_results.append(row)

        # Consultar Presencia
        cursor.execute("""
        SELECT 'presencia' as type, * FROM tabla_presencia
        ORDER BY timestamp DESC
        LIMIT ?
        """, (limit//3,))

        presencia_results = []
        for row in cursor.fetchall():
            row = dict(row)
            row['type'] = 'presencia'
            presencia_results.append(row)

        # Combinar resultados y ordenar por timestamp
        all_results = osint_results + radar_results + centinela_results + presencia_results
        all_results.sort(key=lambda x: x['timestamp'], reverse=True)

        return all_results[:limit]

# Inicializar la base de datos al importar el módulo
init_database()