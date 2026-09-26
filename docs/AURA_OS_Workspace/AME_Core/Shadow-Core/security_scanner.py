"""
security_scanner.py - Active Threat Scanner para AURA
Escanea APIs de vulnerabilidades abiertas cada hora, clasifica con LLM
y dispara alertas críticas en el dashboard.
"""

import os
import json
import time
import re
import logging
from datetime import datetime, timedelta
from threading import Thread, Event
from typing import Dict, Any, List, Optional
import requests
from logging.handlers import RotatingFileHandler
import glob

# Configuración del logger
logging.basicConfig(level=logging.INFO, encoding='utf-8')
logger = logging.getLogger(__name__)
logger.handlers.clear()
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Log rotativo
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
handler = RotatingFileHandler(
    os.path.join(log_dir, 'security_scanner.log'),
    maxBytes=1000000, backupCount=5
)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# ===== CONFIGURACIÓN =====
SCANNER_CONFIG = {
    'interval_hours': 1,  # 1 hora entre barridos completos
    'nvd_api_base': 'https://services.nvd.nist.gov/rest/json/cves/2.0',
    'timeout': 30,  # segundos por solicitud HTTP
    'max_results_per_query': 20,
    'days_lookback': 7,  # buscar CVEs de los últimos 7 días
}

# Tecnologías a monitorear por defecto (se actualizan desde Obsidian)
MONITORED_TECHNOLOGIES = [
    'apache', 'nginx', 'linux', 'windows', 'openssh', 'openssl',
    'wordpress', 'mysql', 'postgresql', 'php', 'python', 'nodejs',
    'docker', 'kubernetes', 'git', 'java', 'tomcat', 'nginx',
    'fortinet', 'cisco', 'paloalto', 'vmware', 'exchange',
]

# Palabras clave críticas para alertas inmediatas
CRITICAL_KEYWORDS = [
    'remote code execution', 'rce', 'zero-day', 'zeroday', 'wormable',
    'critical vulnerability', 'cvss 10', 'cvss 9.', 'actively exploited',
    'exploit in the wild', 'ransomware', 'data breach',
]

# Evento para detener el scanner
_stop_event = Event()

# ===== COLECTOR DE TECNOLOGÍAS DESDE OBSIDIAN =====
def load_technologies_from_obsidian(obsidian_path: Optional[str] = None) -> List[str]:
    """
    Escanea la carpeta AURA_OSINT de Obsidian y extrae tecnologías mencionadas.
    """
    if obsidian_path is None:
        # Ruta por defecto
        base = os.path.expanduser("~/Documents/Obsidian/Vault/AURA_OSINT")
        if not os.path.exists(base):
            # Intentar desde config.json
            try:
                config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "AURA_Core", "config.json")
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                    if 'obsidian_vault_path' in config:
                        base = os.path.join(os.path.expanduser(config['obsidian_vault_path']), "AURA_OSINT")
            except:
                pass
        if not os.path.exists(base):
            return MONITORED_TECHNOLOGIES.copy()
    else:
        base = obsidian_path

    techs = set(MONITORED_TECHNOLOGIES)
    try:
        # Buscar archivos .md
        md_files = glob.glob(os.path.join(base, "*.md"))
        for filepath in md_files:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().lower()

            # Extraer palabras que parezcan software/vulnerabilidades
            patterns = [
                r'\b(?:cve-20\d{2}-\d{4,7})\b',
                r'\b(?:apache|nginx|linux|windows|openssh|openssl)\b',
                r'\b(?:wordpress|mysql|postgresql|php|python|nodejs)\b',
                r'\b(?:docker|kubernetes|git|java|tomcat)\b',
                r'\b(?:fortinet|cisco|paloalto|vmware|exchange)\b',
                r'\b(?:ubuntu|debian|centos|red.?hat|fedora)\b',
                r'\b(?:mongodb|redis|elasticsearch|kafka)\b',
                r'\b(?:aws|azure|gcp|cloudflare|fastly)\b',
            ]
            for pat in patterns:
                matches = re.findall(pat, content)
                for m in matches:
                    techs.add(m.lower())

        logger.info(f"Tecnologías cargadas desde Obsidian: {len(techs)}")
    except Exception as e:
        logger.warning(f"Error cargando tecnologías desde Obsidian: {e}")

    return sorted(techs)

# ===== CONSULTA A NVD API =====
def query_nvd_vulnerabilities(tech_name: str, days_back: int = 7) -> List[Dict]:
    """
    Consulta la API pública de NVD (National Vulnerability Database)
    para CVEs relacionadas con una tecnología específica.
    """
    try:
        # Calcular fecha de inicio (days_back días atrás)
        start_date = (datetime.utcnow() - timedelta(days=days_back)).strftime('%Y-%m-%dT%H:%M:%S.000')
        end_date = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000')

        # Construir keyword search
        params = {
            'keywordSearch': tech_name,
            'pubStartDate': start_date,
            'pubEndDate': end_date,
            'resultsPerPage': SCANNER_CONFIG['max_results_per_query'],
        }

        # Intentar con API key del entorno si existe (mejora límites de rate)
        api_key = os.getenv('NVD_API_KEY', '')
        headers = {}
        if api_key:
            headers['apiKey'] = api_key

        response = requests.get(
            SCANNER_CONFIG['nvd_api_base'],
            params=params,
            headers=headers,
            timeout=SCANNER_CONFIG['timeout']
        )

        if response.status_code == 200:
            data = response.json()
            vulnerabilities = data.get('vulnerabilities', [])
            logger.debug(f"NVD query '{tech_name}': {len(vulnerabilities)} CVEs encontrados")
            return vulnerabilities
        elif response.status_code == 403:
            logger.warning(f"NVD rate limit alcanzado para '{tech_name}'. Esperando...")
            time.sleep(6)  # Esperar antes de reintentar
            return []
        else:
            logger.warning(f"NVD error {response.status_code} para '{tech_name}'")
            return []

    except Exception as e:
        logger.error(f"Error consultando NVD para '{tech_name}': {e}")
        return []

def extract_cve_info(cve_item: Dict) -> Optional[Dict]:
    """
    Extrae información relevante de un item CVE de la API de NVD.
    """
    try:
        cve = cve_item.get('cve', {})
        cve_id = cve.get('id', '')
        descriptions = cve.get('descriptions', [])
        description = ''
        for desc in descriptions:
            if desc.get('lang') == 'en':
                description = desc.get('value', '')
                break
        if not description:
            description = descriptions[0].get('value', '') if descriptions else ''

        metrics = cve.get('metrics', {})
        cvss_score = 0.0
        cvss_severity = 'UNKNOWN'

        # Intentar CVSS v3.1 primero
        for key in ['cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2']:
            if key in metrics and metrics[key]:
                cvss_data = metrics[key][0].get('cvssData', {})
                cvss_score = cvss_data.get('baseScore', 0)
                cvss_severity = cvss_data.get('baseSeverity', 'UNKNOWN')
                break

        published = cve.get('published', '')

        return {
            'id': cve_id,
            'description': description,
            'cvss_score': cvss_score,
            'cvss_severity': cvss_severity,
            'published': published,
            'source': 'nvd',
            'timestamp': datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.warning(f"Error extrayendo info CVE: {e}")
        return None

# ===== CLASIFICACIÓN CON HEURÍSTICAS + LLM =====
def classify_vulnerability(cve_info: Dict) -> Dict:
    """
    Clasifica una vulnerabilidad usando heurísticas rápidas (para cuando el LLM no esté disponible).
    """
    desc = (cve_info.get('description', '') or '').lower()
    cvss = cve_info.get('cvss_score', 0)
    severity = cve_info.get('cvss_severity', 'UNKNOWN').upper()

    # Detectar criticidad por CVSS + palabras clave
    is_critical = False
    threat_level = 3  # default bajo
    tags = []

    # Palabras clave críticas
    for kw in CRITICAL_KEYWORDS:
        if kw in desc:
            is_critical = True
            threat_level = max(threat_level, 8)
            tags.append(kw.replace(' ', '_'))

    # Por CVSS score
    if cvss >= 9.0:
        threat_level = max(threat_level, 9)
        is_critical = True
        tags.append('cvss_critical')
    elif cvss >= 7.0:
        threat_level = max(threat_level, 6)
        tags.append('cvss_high')
    elif cvss >= 4.0:
        threat_level = max(threat_level, 4)
        tags.append('cvss_medium')
    else:
        tags.append('cvss_low')

    # Extraer tecnología afectada
    affected_tech = 'unknown'
    for tech in MONITORED_TECHNOLOGIES:
        if tech in desc:
            affected_tech = tech
            break

    # Generar resumen táctico
    if is_critical:
        resumen = (f"🚨 ALERTA CRÍTICA: {cve_info.get('id', 'CVE-XXXX')} - "
                   f"CVSS {cvss} - {cve_info.get('description', '')[:200]}")
    else:
        resumen = (f"📡 {cve_info.get('id', 'CVE-XXXX')} - CVSS {cvss} - "
                   f"{cve_info.get('description', '')[:150]}")

    return {
        'resumen_tactico': resumen,
        'nivel_amenaza': threat_level,
        'tags': list(set(tags)),
        'is_critical': is_critical,
        'affected_technology': affected_tech,
        'cve_id': cve_info.get('id', ''),
        'cvss_score': cvss,
        'cvss_severity': severity,
        'description': cve_info.get('description', ''),
        'published': cve_info.get('published', ''),
        'source': cve_info.get('source', 'nvd'),
        'clasificador': 'heuristico',
    }

# ===== GENERADOR DE ALERTAS PARA EL DASHBOARD =====
def generate_alert_from_scan(cve_info: Dict, classification: Dict) -> Optional[Dict]:
    """
    Convierte un hallazgo del scanner en una alerta compatible con el dashboard.
    """
    try:
        is_critical = classification.get('is_critical', False)
        threat_level = classification.get('nivel_amenaza', 3)

        # Determinar severidad
        if is_critical or threat_level >= 8:
            severity = 'critical'
            color = '#FF0000'
        elif threat_level >= 6:
            severity = 'high'
            color = '#FF5722'
        elif threat_level >= 4:
            severity = 'medium'
            color = '#FFC107'
        else:
            severity = 'low'
            color = '#4CAF50'

        alert = {
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'active_threat_scanner',
            'id': f"scan_{cve_info.get('id', 'CVE-XXXX')}_{int(time.time())}",
            'type': classification.get('affected_technology', 'unknown'),
            'severity': severity,
            'color': color,
            'title': f"{'🚨 CRÍTICO' if is_critical else '📡'} {cve_info.get('id', 'CVE-XXXX')}",
            'description': classification.get('resumen_tactico', ''),
            'details': [
                {'type': 'cve', 'value': cve_info.get('id', '')},
                {'type': 'cvss', 'value': cve_info.get('cvss_score', 0)},
                {'type': 'severity', 'value': severity},
                {'type': 'published', 'value': cve_info.get('published', '')},
                {'type': 'technology', 'value': classification.get('affected_technology', 'unknown')},
                {'type': 'tags', 'value': classification.get('tags', [])},
            ],
            'affected_nodes': [
                f"AURA/threat_scanner/{cve_info.get('id', 'CVE-XXXX')}.md",
                f"AURA/active_threats/{classification.get('affected_technology', 'unknown')}.md",
            ],
            'metadata': {
                'cve_id': cve_info.get('id', ''),
                'cvss_score': cve_info.get('cvss_score', 0),
                'confidence': 0.85,
                'last_seen': datetime.utcnow().isoformat(),
                'is_critical': is_critical,
                'scanner_type': 'nvd_api',
            },
            'flash_red': is_critical,  # Indicador para nodos parpadeando en rojo
            'action_required': is_critical or threat_level >= 6,
            'action_type': 'save_to_obsidian',
            'action_target': cve_info.get('id', ''),
        }
        return alert
    except Exception as e:
        logger.error(f"Error generando alerta: {e}")
        return None

# ===== ESCANEO COMPLETO =====
def run_full_scan(obsidian_path: Optional[str] = None, callback=None) -> List[Dict]:
    """
    Ejecuta un barrido completo: carga tecnologías, consulta NVD y clasifica.
    Retorna lista de alertas generadas.
    """
    logger.info("=" * 60)
    logger.info("INICIANDO BARRIDO DE AMENAZAS ACTIVO")
    logger.info(f"Hora: {datetime.utcnow().isoformat()}")

    # 1. Cargar tecnologías desde Obsidian
    technologies = load_technologies_from_obsidian(obsidian_path)
    logger.info(f"Tecnologías a escanear: {len(technologies)}")

    # 2. Consultar NVD para cada tecnología
    all_cves = []
    for i, tech in enumerate(technologies):
        if _stop_event.is_set():
            logger.warning("Scanner detenido durante barrido.")
            break

        logger.info(f"Escaneando [{i+1}/{len(technologies)}]: {tech}")
        raw_cves = query_nvd_vulnerabilities(tech, days_back=SCANNER_CONFIG['days_lookback'])

        for item in raw_cves:
            cve_info = extract_cve_info(item)
            if cve_info:
                all_cves.append(cve_info)

        # Pausa entre consultas para no ser rate-limited
        if i < len(technologies) - 1:
            time.sleep(1.5)

    logger.info(f"Total CVEs encontrados: {len(all_cves)}")

    # 3. Clasificar cada CVE
    alerts = []
    critical_count = 0
    for cve_info in all_cves[:50]:  # Limitar a 50 por pasada
        classification = classify_vulnerability(cve_info)
        alert = generate_alert_from_scan(cve_info, classification)
        if alert:
            alerts.append(alert)
            if classification.get('is_critical', False):
                critical_count += 1

    logger.info(f"Alertas generadas: {len(alerts)} (críticas: {critical_count})")

    # 4. Llamar al callback si existe (para integrar con data_feed.py)
    if callback and alerts:
        try:
            callback(alerts)
        except Exception as e:
            logger.error(f"Error en callback del scanner: {e}")

    # 5. Registrar en log resumido
    logger.info(f"BARRIDO COMPLETADO - {len(alerts)} alertas, {critical_count} críticas")
    logger.info("=" * 60)

    return alerts

# ===== CICLO AUTOMÁTICO (CRON INTERNO) =====
def start_scanner_loop(obsidian_path: Optional[str] = None, callback=None):
    """
    Inicia el ciclo automático de escaneo cada hora.
    """
    global _stop_event
    _stop_event.clear()

    logger.info(f"Ciclo de escaneo iniciado: cada {SCANNER_CONFIG['interval_hours']} hora(s)")

    def loop():
        # Primera ejecución inmediata
        run_full_scan(obsidian_path, callback)

        while not _stop_event.is_set():
            # Esperar el intervalo configurado
            next_run = datetime.now() + timedelta(hours=SCANNER_CONFIG['interval_hours'])
            logger.info(f"Próximo barrido programado para: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

            # Esperar con chequeo de stop cada 30 segundos
            check_interval = 30
            remaining = int(timedelta(hours=SCANNER_CONFIG['interval_hours']).total_seconds())
            while remaining > 0 and not _stop_event.is_set():
                sleep_time = min(check_interval, remaining)
                time.sleep(sleep_time)
                remaining -= sleep_time

            if _stop_event.is_set():
                break

            # Ejecutar barrido
            run_full_scan(obsidian_path, callback)

        logger.info("Ciclo de escaneo detenido.")

    thread = Thread(target=loop, daemon=True)
    thread.start()
    return thread

def stop_scanner_loop():
    """Detiene el ciclo de escaneo."""
    global _stop_event
    _stop_event.set()
    logger.info("Señal de detención enviada al scanner.")

# ===== INTEGRACIÓN CON DATA_FEED =====
def create_callback_for_data_feed(socketio_instance=None):
    """
    Crea un callback para enviar alertas del scanner al data_feed.
    """
    def callback(alerts):
        if not alerts:
            return

        # Separar críticas del resto
        critical_alerts = [a for a in alerts if a.get('flash_red', False) or a.get('metadata', {}).get('is_critical', False)]
        normal_alerts = [a for a in alerts if a not in critical_alerts]

        # Enviar las críticas primero
        for alert in critical_alerts:
            alert['priority'] = 'immediate'
            if socketio_instance:
                try:
                    socketio_instance.emit('new_alert', alert, room='global')
                    socketio_instance.emit('new_alert', alert, room='security')
                    socketio_instance.emit('new_alert', alert, room='threat')
                    # Evento especial para parpadeo rojo
                    socketio_instance.emit('critical_threat_alert', {
                        'alert': alert,
                        'flash_color': '#FF0000',
                        'flash_duration': 5000,
                        'nodes': alert.get('affected_nodes', []),
                    })
                    logger.warning(f"🚨 ALERTA CRÍTICA ENVIADA AL DASHBOARD: {alert.get('title', '')}")
                except Exception as e:
                    logger.error(f"Error emitiendo alerta crítica: {e}")

            # Si no hay socketio, registrar en log
            else:
                logger.warning(f"🚨 CRÍTICA (sin socket): {alert.get('title', '')}")

        # Enviar las normales
        for alert in normal_alerts:
            alert['priority'] = 'normal'
            if socketio_instance:
                try:
                    socketio_instance.emit('new_alert', alert, room='global')
                    socketio_instance.emit('new_alert', alert, room='security')
                    logger.info(f"📡 Alerta de escaneo enviada: {alert.get('title', '')}")
                except Exception as e:
                    logger.error(f"Error emitiendo alerta normal: {e}")

    return callback

# ===== PUNTO DE ENTRADA PARA TESTING =====
if __name__ == "__main__":
    print("=== ACTIVE THREAT SCANNER - TEST ===")
    print(f"Iniciando escaneo único... (Ctrl+C para detener)")
    alerts = run_full_scan()
    print(f"\nResumen: {len(alerts)} alertas generadas.")
    print("=" * 40)
    for a in alerts:
        icon = "🚨" if a.get('flash_red') else "📡"
        print(f"{icon} {a.get('title', '')} - {a.get('severity', '')}")