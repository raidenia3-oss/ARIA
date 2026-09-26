"""
user_learning_profile.py - Perfil de aprendizaje del usuario para AURA
Analiza agent_decisions.log y genera un perfil de preferencias automático
para que el Decision Core ajuste su comportamiento.
"""

import os
import json
import re
import logging
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Ruta al archivo de decisiones
LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agent_decisions.log")

# Umbrales de aprendizaje
LEARNING_RULES = {
    'auto_mute_count': 3,        # 3 rechazos → auto-mute
    'boost_priority_count': 3,   # 3 aprobaciones → subir prioridad
    'max_history_days': 30,      # Solo analizar últimos 30 días
    'profile_version': 1,        # Versión del perfil
}

# ===== ANALIZADOR DE LOG =====
def parse_decision_log(log_path: Optional[str] = None) -> List[Dict]:
    """
    Parsea el archivo agent_decisions.log y extrae cada decisión como un dict.
    """
    path = log_path or LOG_PATH
    decisions = []

    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        current_entry = {}
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue  # Saltar cabeceras y líneas vacías

            # Formato esperado: TIMESTAMP - LEVEL - MESSAGE
            # Intentar parsear líneas con formato estructurado
            match = re.match(
                r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s*-\s*'
                r'(\w+)\s*-\s*(.+)',
                line
            )
            if match:
                # Si hay una entrada anterior pendiente, guardarla
                if current_entry:
                    decisions.append(current_entry)

                current_entry = {
                    'timestamp': match.group(1),
                    'level': match.group(2),
                    'message': match.group(3).strip(),
                }
            elif current_entry:
                # Continuación de la entrada anterior
                current_entry['message'] += ' ' + line

        # Guardar la última entrada
        if current_entry:
            decisions.append(current_entry)

        logger.info(f"Log parseado: {len(decisions)} decisiones encontradas")
        return decisions

    except FileNotFoundError:
        logger.warning(f"Archivo de log no encontrado: {path}. Creando uno nuevo.")
        _init_log_file(path)
        return []
    except Exception as e:
        logger.error(f"Error parseando log: {e}")
        return []

def _init_log_file(path: str):
    """Inicializa el archivo de log si no existe."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# Log de decisiones del agente AURA\n")
        f.write(f"# Iniciado: {datetime.utcnow().isoformat()}\n")
        f.write("# ============================================\n")
        f.write("# Formato: TIMESTAMP - LEVEL - MESSAGE\n")
        f.write("# LEVELS: APPROVED, REJECTED, AUTO, INFO, WARN, ERROR\n")
        f.write("# Mensajes contienen: decision_id | tipo | nivel_amenaza | fuente | título\n")
        f.write("# ============================================\n")

# ===== EXTRACCIÓN DE PATRONES =====
def extract_decision_patterns(decisions: List[Dict]) -> Dict:
    """
    Extrae patrones de decisiones: qué tipos se aprueban/rechazan, con qué frecuencia.
    """
    approved = Counter()
    rejected = Counter()
    auto_bypassed = Counter()
    approval_by_alert_type = defaultdict(lambda: {'approved': 0, 'rejected': 0, 'auto': 0})
    approval_by_threat_level = defaultdict(lambda: {'approved': 0, 'rejected': 0, 'auto': 0})
    approval_by_source = defaultdict(lambda: {'approved': 0, 'rejected': 0, 'auto': 0})
    daily_patterns = defaultdict(lambda: {'approved': 0, 'rejected': 0, 'auto': 0})
    total_by_level = {'INFO': 0, 'APPROVED': 0, 'REJECTED': 0, 'AUTO': 0, 'WARN': 0}

    for dec in decisions:
        level = dec.get('level', 'INFO')
        msg = dec.get('message', '')

        # Extraer metadatos del mensaje estructurado
        tipo = _extract_field(msg, 'tipo') or _extract_field(msg, 'type') or 'unknown'
        fuente = _extract_field(msg, 'fuente') or _extract_field(msg, 'source') or 'unknown'
        amenaza_str = _extract_field(msg, 'nivel_amenaza') or _extract_field(msg, 'threat_level') or ''
        try:
            amenaza = int(float(amenaza_str)) if amenaza_str else 0
        except:
            amenaza = 0
        titulo = _extract_field(msg, 'titulo') or _extract_field(msg, 'title') or 'desconocido'

        # Contar por nivel
        total_by_level[level] = total_by_level.get(level, 0) + 1

        # Clasificar
        if level == 'APPROVED' or 'APROBADA' in msg.upper():
            approved[tipo] += 1
            approval_by_alert_type[tipo]['approved'] += 1
            if amenaza > 0:
                approval_by_threat_level[amenaza]['approved'] += 1
            approval_by_source[fuente]['approved'] += 1
        elif level == 'REJECTED' or 'RECHAZADA' in msg.upper():
            rejected[tipo] += 1
            approval_by_alert_type[tipo]['rejected'] += 1
            if amenaza > 0:
                approval_by_threat_level[amenaza]['rejected'] += 1
            approval_by_source[fuente]['rejected'] += 1
        elif level == 'AUTO' or 'AUTO-EJECUTADA' in msg.upper():
            auto_bypassed[tipo] += 1
            approval_by_alert_type[tipo]['auto'] += 1
            if amenaza > 0:
                approval_by_threat_level[amenaza]['auto'] += 1

        # Patrón diario
        try:
            day = dec['timestamp'][:10] if 'T' in dec.get('timestamp', '') else datetime.utcnow().strftime('%Y-%m-%d')
        except:
            day = datetime.utcnow().strftime('%Y-%m-%d')
        if level in ('APPROVED', 'REJECTED', 'AUTO'):
            key = 'approved' if level == 'APPROVED' else 'rejected' if level == 'REJECTED' else 'auto'
            daily_patterns[day][key] += 1

    return {
        'approved': dict(approved),
        'rejected': dict(rejected),
        'auto': dict(auto_bypassed),
        'by_type': dict(approval_by_alert_type),
        'by_threat_level': {str(k): v for k, v in sorted(approval_by_threat_level.items())},
        'by_source': dict(approval_by_source),
        'daily': dict(daily_patterns),
        'total_by_level': total_by_level,
        'total_decisions': len(decisions),
    }

def _extract_field(message: str, field: str) -> Optional[str]:
    """Extrae el valor de un campo en un mensaje estructurado."""
    patterns = [
        rf'{field}:\s*([^\s|,;\]]+)',
        rf'{field}=([^\s|,;\]]+)',
        rf'"{field}":\s*"([^"]+)"',
    ]
    for pat in patterns:
        match = re.search(pat, message, re.IGNORECASE)
        if match:
            return match.group(1)
    return None

# ===== GENERACIÓN DEL PERFIL =====
def generate_user_profile(decisions: Optional[List[Dict]] = None) -> Dict:
    """
    Genera el perfil de usuario basado en el historial de decisiones.
    """
    if decisions is None:
        decisions = parse_decision_log()

    patterns = extract_decision_patterns(decisions)

    # Determinar auto-mute: tipos rechazados >= umbral
    auto_mute_types = []
    for tipo, count in patterns['rejected'].items():
        if count >= LEARNING_RULES['auto_mute_count']:
            auto_mute_types.append({
                'type': tipo,
                'rejected_count': count,
                'reason': f'Rechazada {count} veces (umbral: {LEARNING_RULES["auto_mute_count"]})'
            })

    # Determinar prioridad aumentada: tipos aprobados >= umbral
    boosted_types = []
    for tipo, count in patterns['approved'].items():
        if count >= LEARNING_RULES['boost_priority_count']:
            boosted_types.append({
                'type': tipo,
                'approved_count': count,
                'priority_boost': min(count * 0.5, 3.0),  # hasta +3 de prioridad
                'reason': f'Aprobada {count} veces (umbral: {LEARNING_RULES["boost_priority_count"]})'
            })

    # Calcular tasa de aprobación general
    total_approved = sum(patterns['approved'].values())
    total_rejected = sum(patterns['rejected'].values())
    total_manual = total_approved + total_rejected
    approval_rate = (total_approved / total_manual * 100) if total_manual > 0 else 50.0

    # Preferencias por nivel de amenaza
    threat_preferences = {}
    for nivel, data in patterns['by_threat_level'].items():
        total = data['approved'] + data['rejected']
        if total > 0:
            rate = (data['approved'] / total * 100)
            threat_preferences[nivel] = {
                'approval_rate': round(rate, 1),
                'total': total,
                'approved': data['approved'],
                'rejected': data['rejected'],
            }

    profile = {
        'generated_at': datetime.utcnow().isoformat(),
        'profile_version': LEARNING_RULES['profile_version'],
        'total_decisions_analyzed': patterns['total_decisions'],
        'approval_rate': round(approval_rate, 1),
        'auto_mute_types': auto_mute_types,
        'boosted_types': boosted_types,
        'patterns': patterns,
        'threat_preferences': threat_preferences,
        'learning_rules': LEARNING_RULES,
    }

    logger.info(f"Perfil de usuario generado: {len(auto_mute_types)} auto-mute, "
                f"{len(boosted_types)} prioridad aumentada, "
                f"tasa aprobación: {approval_rate:.1f}%")

    return profile

# ===== APLICACIÓN DEL PERFIL AL DECISION CORE =====
def get_learning_adjustments(profile: Dict) -> Dict:
    """
    Convierte el perfil en ajustes concretos para el Decision Core.
    """
    adjustments = {
        'auto_mute': {},        # {tipo: True} → descartar automáticamente
        'priority_boost': {},   # {tipo: factor} → multiplicador de prioridad
        'ghost_mode_threshold': None,  # Ajuste del umbral de Ghost Mode si aplica
    }

    # Auto-mute: tipos a descartar
    for item in profile.get('auto_mute_types', []):
        adjustments['auto_mute'][item['type']] = True
        logger.info(f"📛 AUTO-MUTE activado para tipo: {item['type']}")

    # Prioridad aumentada
    for item in profile.get('boosted_types', []):
        adjustments['priority_boost'][item['type']] = item['priority_boost']
        logger.info(f"⬆ PRIORIDAD AUMENTADA para tipo: {item['type']} (+{item['priority_boost']})")

    # Ajuste del umbral de Ghost Mode basado en tasa de aprobación
    approval_rate = profile.get('approval_rate', 50)
    if approval_rate >= 80:
        # Usuario muy permisivo → subir umbral a 6 (Ghost Mode más seguro)
        adjustments['ghost_mode_threshold'] = 6
        logger.info(f"👻 Umbral Ghost Mode ajustado a 6 (tasa aprobación: {approval_rate}%)")
    elif approval_rate <= 30:
        # Usuario muy restrictivo → bajar umbral a 3 (Ghost Mode más permisivo)
        adjustments['ghost_mode_threshold'] = 3
        logger.info(f"👻 Umbral Ghost Mode ajustado a 3 (tasa aprobación: {approval_rate}%)")
    else:
        # Neutro → mantener umbral por defecto
        adjustments['ghost_mode_threshold'] = 4
        logger.info(f"👻 Umbral Ghost Mode: 4 (por defecto, tasa aprobación: {approval_rate}%)")

    return adjustments

# ===== REGISTRO DE DECISIONES EN EL LOG =====
def log_decision(decision_type: str, data: Dict):
    """
    Registra una decisión del usuario en agent_decisions.log.
    """
    try:
        path = LOG_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)

        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        tipo = data.get('type', data.get('tipo', 'unknown'))
        fuente = data.get('source', data.get('fuente', 'unknown'))
        nivel = data.get('threat_level', data.get('nivel_amenaza', '?'))
        titulo = data.get('title', data.get('titulo', 'desconocido'))

        log_line = (
            f"{timestamp} - {decision_type} - "
            f"decision_id={data.get('id', '?')} | "
            f"tipo={tipo} | "
            f"nivel_amenaza={nivel} | "
            f"fuente={fuente} | "
            f"titulo={titulo[:50]}\n"
        )

        with open(path, 'a', encoding='utf-8') as f:
            f.write(log_line)

        logger.debug(f"Decisión registrada: {decision_type} - {titulo[:30]}")
        return True
    except Exception as e:
        logger.error(f"Error registrando decisión: {e}")
        return False

# ===== PUNTO DE ENTRADA =====
def generate_and_save_profile(output_path: Optional[str] = None) -> Dict:
    """
    Genera el perfil y lo guarda como JSON para que el Decision Core lo lea.
    """
    profile = generate_user_profile()
    adjustments = get_learning_adjustments(profile)

    result = {
        'profile': profile,
        'adjustments': adjustments,
        'generated_at': datetime.utcnow().isoformat(),
    }

    if output_path is None:
        output_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "AURA_Core",
            "user_profile.json"
        )

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        logger.info(f"Perfil guardado en: {output_path}")
    except Exception as e:
        logger.error(f"Error guardando perfil: {e}")

    return result

# ===== SHOW SUMMARY =====
def print_profile_summary(profile: Dict):
    """Muestra un resumen del perfil generado."""
    print("\n" + "=" * 60)
    print("📊 PERFIL DE APRENDIZAJE DE USUARIO - AURA")
    print("=" * 60)
    print(f"📅 Generado: {profile.get('generated_at', '?')[:19]}")
    print(f"📈 Decisiones analizadas: {profile.get('total_decisions_analyzed', 0)}")
    print(f"✅ Tasa de aprobación: {profile.get('approval_rate', '?')}%")
    print()

    adjustments = profile.get('adjustments', {})
    auto_mute = adjustments.get('auto_mute', {})
    boosts = adjustments.get('priority_boost', {})

    print("📛 AUTO-MUTE activos:")
    if auto_mute:
        for tipo in auto_mute:
            print(f"   🔇 {tipo}")
    else:
        print("   (ninguno aún - necesitas rechazar 3 del mismo tipo)")

    print("\n⬆ PRIORIDAD AUMENTADA:")
    if boosts:
        for tipo, boost in boosts.items():
            print(f"   ⬆ {tipo} (+{boost:.1f})")
    else:
        print("   (ninguno aún - necesitas aprobar 3 del mismo tipo)")

    print(f"\n👻 Umbral Ghost Mode: {adjustments.get('ghost_mode_threshold', 4)}")
    print("=" * 60)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = generate_and_save_profile()
    print_profile_summary(result)